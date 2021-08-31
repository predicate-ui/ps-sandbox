from pathlib import Path
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from google.auth.exceptions import RefreshError
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from json import JSONDecodeError
import email
from base64 import urlsafe_b64decode, urlsafe_b64encode
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.audio import MIMEAudio
import os
from email.mime.image import MIMEImage
from email.mime.base import MIMEBase
import mimetypes

# If modifying these scopes, delete the file token.json.
SCOPES = ["modify"]
CRED_PATH = Path("gmapi/IndecorEmailBot.json")
TOKEN_PATH = Path("token.json")


class GmailUser:
    def __init__(
        self,
        user_id: str,
        cred_path="credentials.json",
        token_path="token.json",
        scopes=["send"],
    ):
        # using Path objects to hold credential paths
        self.user_id = user_id
        self.cred_path = Path(cred_path)
        self.token_path = Path(token_path)
        self.scopes = [
            f"https://www.googleapis.com/auth/gmail.{scope}" for scope in scopes
        ]
        # full scope encapsulates all other scopes
        if "full" in self.scopes:
            self.scopes = ["https://mail.google.com/"]

        self.creds = self._get_creds()
        self._service = self.start_service()

    def _read_token(self):
        if self.token_path.exists():
            try:
                return Credentials.from_authorized_user_file(
                    self.token_path.absolute(), SCOPES
                )
            except JSONDecodeError:
                self.wipe_token()

    def _write_token(self, creds):
        with self.token_path.open("w") as token_file:
            token_file.write(creds.to_json())

    def _refresh_token(self, creds):
        if creds and creds.expired and creds.refresh_token:
            try:
                creds.refresh(Request())
                self._write_token(creds)
                return creds
            except:
                # TODO find exception name
                self.wipe_token()
        return None

    def wipe_token(self):
        self.token_path.unlink()

    def _generate_creds(self):
        flow = InstalledAppFlow.from_client_secrets_file(self.cred_path, self.scopes)
        creds = flow.run_local_server(port=0)
        self._write_token(creds)
        return creds

    def _get_creds(self):
        # If we have user access and refresh tokens, use those. Otherwise, generate
        # them from the OAuth credentials
        creds = self._read_token()

        # If there are no (valid) credentials available, let the user log in.
        if creds and not creds.valid:
            creds = self._refresh_token(creds)
        if not creds:
            creds = self._generate_creds()
        return creds

    def start_service(self):
        # TODO log starting a new service
        print("starting a new service")
        service = build("gmail", "v1", credentials=self.creds)
        return service

    def valid_service(self):
        if self._service:
            try:
                return bool(
                    self._service.users().getProfile(userId=self.user_id).execute()
                )
            except (HttpError, RefreshError):
                # TODO any other errors that can be returned here?
                return False
        else:
            return False

    def get_service(self):
        if not self.valid_service():
            self._service = self.start_service()
        return self._service

    def _messages_api(self):
        return self.get_service().users().messages()

    def list_messages(
        self,
        labels=None,
        query=None,
        page_token=None,
        max_results=None,
        include_spam_and_trash=None,
    ):
        return (
            self._messages_api()
            .list(
                userId=self.user_id,
                labelIds=labels,
                q=query,
                pageToken=page_token,
                maxResults=max_results,
                includeSpamTrash=include_spam_and_trash,
            )
            .execute()
        )

    def get_message(self, message_id):
        return GMessage(GmailUser=self, message_id=message_id)

    def get_messages(
        self,
        labels=None,
        query=None,
        page_token=None,
        max_results=None,
        include_spam_and_trash=None,
    ):
        return [
            self.get_message(message["id"])
            for message in self.list_messages(
                labels=labels,
                query=query,
                page_token=page_token,
                max_results=max_results,
                include_spam_and_trash=include_spam_and_trash,
            )["messages"]
        ]

    def create_message(
        self, to: str, subject: str, message_text: str, file: str = None
    ):
        if not file:
            message = self._create_text_message(to, subject, message_text)
        else:
            message = self._create_attachment_message(to, subject, message_text, file)
        # Not making a new subclass just for this attirbute
        # but need to initialize the variable for replies
        message.threadId = None
        return message

    def create_reply(self, reply_to: "GMessage", message_text: str, file: str = None):
        subject = reply_to.mime["Subject"]
        if "Re: " != subject[:4]:
            subject = "Re: " + subject
        to = reply_to.mime["From"]
        reply_mes = self.create_message(
            to=to, subject=subject, message_text=message_text, file=file
        )

        reply_mes.threadId = reply_to.threadId

        reply_id = reply_to.mime.get("Message-ID", "")
        references = reply_to.mime.get("References")
        if not references:
            references = reply_to.mime["In-Reply-To"]
        if references and reply_id:
            references += f"\t{reply_id}"

        del reply_mes["In-Reply-To"]
        del reply_mes["References"]

        reply_mes["In-Reply-To"] = reply_id
        reply_mes["References"] = references

        return reply_mes

    def _create_text_message(self, to: str, subject: str, message_text: str):
        """Create a message for an email.

        Args:
            to: Email address of the receiver.
            subject: The subject of the email message.
            message_text: The text of the email message.

        Returns:
            An object containing a base64url encoded email object.
        """
        message = email.mime.text.MIMEText(message_text)
        message["to"] = to
        message["from"] = self.user_id
        message["subject"] = subject
        return message

    def _create_attachment_message(
        self, to: str, subject: str, message_text: str, file: str
    ):
        """Create a message for an email.

        Args:
            to: Email address of the receiver.
            subject: The subject of the email message.
            message_text: The text of the email message.
            file: The path to the file to be attached.

        Returns:
            An object containing a base64url encoded email object.
        """
        message = MIMEMultipart()
        message["to"] = to
        message["from"] = self.user_id
        message["subject"] = subject

        msg = MIMEText(message_text)
        message.attach(msg)

        content_type, encoding = mimetypes.guess_type(file)

        if content_type is None or encoding is not None:
            content_type = "application/octet-stream"
        main_type, sub_type = content_type.split("/", 1)
        if main_type == "text":
            fp = open(file, "rb")
            msg = MIMEText(fp.read(), _subtype=sub_type)
            fp.close()
        elif main_type == "image":
            fp = open(file, "rb")
            msg = MIMEImage(fp.read(), _subtype=sub_type)
            fp.close()
        elif main_type == "audio":
            fp = open(file, "rb")
            msg = MIMEAudio(fp.read(), _subtype=sub_type)
            fp.close()
        else:
            fp = open(file, "rb")
            msg = MIMEBase(main_type, sub_type)
            msg.set_payload(fp.read())
            fp.close()
        filename = os.path.basename(file)
        msg.add_header("Content-Disposition", "attachment", filename=filename)
        message.attach(msg)

        return message

    def send_message(self, message):
        """Send an email message.

        Args:
            service: Authorized Gmail API service instance.
            message: MIME Message to be sent.

        Returns:
            Sent Message.
        """

        api_package = {"raw": urlsafe_b64encode(message.as_bytes()).decode()}
        if message.threadId:
            api_package["threadId"] = message.threadId
        api_response = (
            self._messages_api().send(userId=self.user_id, body=api_package).execute()
        )
        return api_response


class GMessage:
    def __init__(self, GmailUser: "GmailUser", message_id):
        self.User = GmailUser
        self.message_id = message_id

        self.original = (
            self.User._messages_api()
            .get(userId=self.User.user_id, id=self.message_id, format="raw")
            .execute()
        )
        self.id = self.original["id"]
        self.threadId = self.original["threadId"]
        self.labels = self.original["labelIds"]
        self.snippet = self.original["snippet"]
        self.raw = self.original["raw"]
        self.historyId = self.original["historyId"]
        self.internalDate = self.original["internalDate"]

        bit_message = urlsafe_b64decode(self.raw)
        self.mime = email.parser.BytesParser(policy=email.policy.SMTP).parsebytes(
            bit_message
        )
        self.subject = self.mime.get("Subject")
        self.body = self.mime.get_body(("plain"))
        self.html_body = self.mime.get_body(("html", "plain"))

    def __repr__(self):
        return str((self.id, self.subject, self.snippet))
