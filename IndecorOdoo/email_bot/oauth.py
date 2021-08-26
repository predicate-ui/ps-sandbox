from pathlib import Path
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from json import JSONDecodeError
import email
from base64 import urlsafe_b64decode


# If modifying these scopes, delete the file token.json.
SCOPES = ['modify']
CRED_PATH = Path('/home/benjamin/predicatestudio/ps-sandbox/IndecorOdoo/email_bot/IndecorEmailBot.json')
TOKEN_PATH = Path("token.json")

class OAuthGmailUser():
    def __init__(self, user_id: str, cred_path="credentials.json", token_path="token.json", scopes=['send']):
        # using Path objects to hold credential paths
        self.user_id = user_id
        self.cred_path = Path(cred_path)
        self.token_path = Path(token_path)
        self.scopes = [f"https://www.googleapis.com/auth/gmail.{scope}" for scope in scopes]
        # full scope encapsulates all other scopes
        if "full" in self.scopes:
            self.scopes = ['https://mail.google.com/']
        
        self.creds = self._get_creds()
        self._service = self.start_service()
    
    def _read_token(self):
        if self.token_path.exists():
            try:
                return Credentials.from_authorized_user_file(self.token_path.absolute(), SCOPES)
            except JSONDecodeError:
                self.wipe_token()

    def _write_token(self, creds):
        with self.token_path.open('w') as token_file:
            token_file.write(creds.to_json())

    def _refresh_token(self, creds):
        if creds and creds.expired and creds.refresh_token:
            try:
                creds.refresh(Request())
                self._write_token(creds)
                return creds
            except:
                #TODO find exception name
                self.wipe_token()
        return None

    def wipe_token(self):
        self.token_path.unlink()


    def _generate_creds(self):
        flow = InstalledAppFlow.from_client_secrets_file(
            self.cred_path, self.scopes)
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
        #TODO log starting a new service
        print("starting a new service")
        service = build('gmail', 'v1', credentials=self.creds)
        return service
    
    def valid_service(self):
        if self._service:
            try:
                return bool(self._service.users().getProfile(userId=self.user_id).execute())
            except HttpError:
                #TODO any other errors that can be returned here?
                return False
        else:
            return False

    def get_service(self):
        if not self.valid_service():
            self._service = self.start_service()
        return self._service

    def _messages_api(self):
        return self.get_service().users().messages()

    def list_messages(self, labels=None, query=None, page_token=None, max_results = None, include_spam_and_trash = None):
        return self._messages_api().list(userId=self.user_id, labelIds=labels, q=query, pageToken=page_token, maxResults=max_results, includeSpamTrash=include_spam_and_trash).execute()

    def get_message(self, message_id):
        return GMessage(GmailUser=self, message_id=message_id)

    def get_messages(self, labels=None, query=None, page_token=None, max_results = None, include_spam_and_trash = None):
        return [self.get_message(message['id']) for message in self.list_messages(labels=labels, query=query, page_token=page_token, max_results = max_results, include_spam_and_trash = include_spam_and_trash)['messages']]


class GMessage():
    def __init__(self, GmailUser: OAuthGmailUser, message_id):
        self.User = GmailUser
        self.message_id = message_id

        self.original = self.User._messages_api().get(userId=self.User.user_id, id=self.message_id, format='raw').execute()
        self.id = self.original['id']
        self.threadId = self.original['threadId']
        self.labels = self.original['labelIds']
        self.snippet = self.original['snippet']
        self.raw = self.original['raw']
        self.historyId = self.original['historyId']
        self.internalDate = self.original['internalDate']

        bit_message = urlsafe_b64decode(self.raw)
        self.mime = email.parser.BytesParser(policy=email.policy.SMTP).parsebytes(bit_message)
        self.headers = dict(self.mime.items())
        self.subject = self.headers['Subject']
        self.body = self.mime.get_body(('plain'))
        self.html_body = self.mime.get_body(('html', 'plain'))
    
    def __repr__(self):
        return str((self.id, self.subject))
        

# def main():
#     """Shows basic usage of the Gmail API.
#     Lists the user's Gmail labels.
#     """
    
#     creds = get_user_token(TOKEN_PATH, SCOPES)


#     service = build('gmail', 'v1', credentials=creds)

#     # Call the Gmail API
#     results = service.users().labels().list(userId='me').execute()
#     labels = results.get('labels', [])

#     if not labels:
#         print('No labels found.')
#     else:
#         print('Labels:')
#         for label in labels:
#             print(label['name'])

# if __name__ == '__main__':
#     main()