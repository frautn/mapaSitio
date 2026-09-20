from django.core.management.base import BaseCommand, CommandError

# import json
import os
import pandas as pd
from pathlib import Path
from dotenv import load_dotenv

from google.oauth2.credentials import Credentials
import gspread

# from main.models import Article

class Command(BaseCommand):
    help = 'Updates the database'

    def add_arguments(self, parser):
        # Optional: Add arguments if your script needs inputs
        parser.add_argument('sample_arg', type=str, nargs='?', default='Hello')

    def handle(self, *args, **options):

        SCOPES = [
            "https://www.googleapis.com/auth/spreadsheets",
            "https://www.googleapis.com/auth/drive",
        ]

        # oauth_client_path = Path.cwd() / "secrets" / "oauth_client.json"
        token_path = Path.cwd() / "secrets" / "token.json"

        # if oauth_client_path.exists():
        #     creds = Credentials.from_authorized_user_file(str(token_path), SCOPES)
        # else:
        #     raise CommandError(
        #         "oauth_client.json not found. Please authenticate and save oauth_client.json in secrets directory."
        #     )

        # Reuse a cached token across runs.
        if token_path.exists():
            creds = Credentials.from_authorized_user_file(str(token_path), SCOPES)
        else:
            raise CommandError(
                "token.json no encontrado. Por favor autentíquese y guarde token.json en el directorio secrets."
            )
            # self.stdout.write(self.style.WARNING(
            #     "token.json not found. Please authenticate and save token.json in secrets directory."
            # ))
            # return

        self.stdout.write("Autenticación exitosa.")

        client = gspread.authorize(creds)
        load_dotenv()  # Automatically finds .env file
        url_sin_detenidos = os.getenv('URL_SIN_DETENIDOS')
        spreadsheet = client.open_by_url(url_sin_detenidos)
        ws = spreadsheet.worksheet('INBOX')
        raw_values = ws.get_all_values()
        headers = ['Fecha_deteccion', 'Medio', 'Titulo', 'Link', 'Keyword_detectada',
                'Fuente', 'Revisado', 'Validado', 'Observaciones', 'Estado_IA',
                'Palabras_detectadas', 'Puntaje', 'archivo', 'Puntaje_solo_titulo', 'otro_2']
        all_records = gspread.utils.to_records(headers, raw_values[1:])
        df_sd = pd.DataFrame(all_records)
        df_sd = df_sd[df_sd['Link'].str.strip().astype(bool)]

        for index, row in df_sd.iterrows():
            archivo = row['archivo']
            if not isinstance(archivo, str) or not archivo.endswith('.txt'):
                continue

            self.stdout.write(f"Archivo {archivo}")
