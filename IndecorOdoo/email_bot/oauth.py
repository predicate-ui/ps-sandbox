from pathlib import Path
from googleapiclient.discovery import build
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials

# If modifying these scopes, delete the file token.json.
SCOPES = ['https://www.googleapis.com/auth/gmail.modify']
CRED_PATH = Path('/home/benjamin/predicatestudio/ps-sandbox/IndecorOdoo/email_bot/IndecorEmailBot.json')
TOKEN_PATH = Path("token.json")


def get_user_token(tokenpath, scopes):
    creds = None
    # The file token.json stores the user's access and refresh tokens, and is
    # created automatically when the authorization flow completes for the first
    # time.
    if tokenpath.exists():
        creds = Credentials.from_authorized_user_file(tokenpath.absolute(), SCOPES)
    # else:
    #     tokenpath.touch()
            
    # If there are no (valid) credentials available, let the user log in.
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(
                CRED_PATH, SCOPES)
            creds = flow.run_local_server(port=0)
        # Save the credentials for the next run
        with tokenpath.open('w') as token:
            token.write(creds.to_json())
    return creds
    
def main():
    """Shows basic usage of the Gmail API.
    Lists the user's Gmail labels.
    """
    
    creds = get_user_token(TOKEN_PATH, SCOPES)


    service = build('gmail', 'v1', credentials=creds)

    # Call the Gmail API
    results = service.users().labels().list(userId='me').execute()
    labels = results.get('labels', [])

    if not labels:
        print('No labels found.')
    else:
        print('Labels:')
        for label in labels:
            print(label['name'])

if __name__ == '__main__':
    main()