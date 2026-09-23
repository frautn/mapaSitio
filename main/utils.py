"""main/utils.py - helper functions used across the app."""
import csv
from http import client
from pathlib import Path
import re
import re
import shutil
import subprocess
import sys
import json
from datetime import datetime
import pandas as pd

from google.oauth2 import service_account
import gspread
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseDownload

from django.utils import timezone

from .models import Article, ArticleContent


def _parse_csv_datetime(raw_value):
    if not raw_value:
        return None

    parsed_value = None
    for candidate_format in ("%Y-%m-%d %H:%M:%S.%f", "%Y-%m-%d %H:%M:%S"):
        try:
            parsed_value = datetime.strptime(raw_value.strip(), candidate_format)
            break
        except ValueError:
            continue

    if parsed_value is None:
        return None

    if timezone.is_naive(parsed_value):
        parsed_value = timezone.make_aware(parsed_value, timezone.get_current_timezone())

    return parsed_value


def _normalize_validado(raw_value):
    if raw_value in {Article.VALIDADO_VALIDO, Article.VALIDADO_NO_RELEVANTE, Article.VALIDADO_SIN_REVISAR}:
        return raw_value
    return Article.VALIDADO_SIN_REVISAR


def import_articles_from_csv(uploaded_file):
    imported_count = 0
    updated_count = 0
    skipped_count = 0

    decoded_file = uploaded_file.read().decode('utf-8-sig').splitlines()
    # 1. Increase the global field size limit
    try:
        csv.field_size_limit(sys.maxsize)
    except OverflowError:
        # Fallback for systems where sys.maxsize exceeds the C long limit
        csv.field_size_limit(2147483647)
    reader = csv.DictReader(decoded_file)

    for row in reader:
        article_id = (row.get('ID') or '').strip()
        if not article_id:
            skipped_count += 1
            continue

        obj = json.loads((row.get('diffbot_response') or '{}').strip())
        json_obj = (obj.get('objects') or [{}])[0]

        article_date = json_obj.get('date')
        if article_date is None:
            article_date_save = row.get('Fecha detección')
        else:
            article_date_save = Article.parse_gnews_date(article_date)

        article, created = Article.objects.update_or_create(
        ID=article_id,
        defaults={
            'date': article_date_save,
            'GNews_title': (row.get('Título') or '').strip()[:500],
            'Diffbot_title': (json_obj.get('title') or '').strip()[:500],
            'siteName': (json_obj.get('siteName') or '').strip()[:200],
            'link': (json_obj.get('resolvedPageUrl') or '').strip(),
            'validado': _normalize_validado(row.get('Validado', '').strip()),
        },
        )

        ArticleContent.objects.update_or_create(
        article=article,
        defaults={
            'html_content': (json_obj.get('html') or 'Sin datos.').strip(),
        },
        )

        if created:
            imported_count += 1
        else:
            updated_count += 1

    return imported_count, updated_count, skipped_count

def download_data(progress_callback=None):
    """Download data from Google Drive and Google Sheets."""

    def report(message):
        if progress_callback:
            progress_callback(message)

    # Spreadsheet URL
    url_sin_detenidos = 'https://docs.google.com/spreadsheets/d/1xKAdnEC8HP4b5MJ-HrOGKqa7cXE-ue336RsWkIAhnYg/edit?gid=762130750#gid=762130750'

    # Folder with articles (Kate - textos)
    url_folder = "https://drive.google.com/drive/u/0/folders/1SF-881n6sA8BIGxnRJ8TD9VWNW2sGeK9"

    SCOPES = [
        "https://www.googleapis.com/auth/spreadsheets",
        "https://www.googleapis.com/auth/drive",
    ]

    service_account_path = Path.cwd() / "secrets" / "service_account.json"

    # The shared folder/spreadsheet must be shared with the service account's email
    creds = service_account.Credentials.from_service_account_file(
        str(service_account_path), scopes=SCOPES
    )

    client = gspread.authorize(creds)

    spreadsheet = client.open_by_url(url_sin_detenidos)
    drive_service = build('drive', 'v3', credentials=creds)

    folder_id = re.search(r"/folders/([^/?]+)", url_folder).group(1)


    download_root = Path("downloads")
    download_root.mkdir(parents=True, exist_ok=True)

    response = drive_service.files().list(
        q=f"'{folder_id}' in parents and name = 'diffbot_responses.tar.gz' and trashed = false",
        fields="files(id, name, mimeType, size)",
        includeItemsFromAllDrives=True,
        supportsAllDrives=True,
    ).execute()

    diffbot_folder = Path(download_root, "diffbot")
    shutil.rmtree(diffbot_folder) if diffbot_folder.exists() else None
    diffbot_folder.mkdir(parents=True, exist_ok=True)
    output_path_json = Path(download_root, "diffbot_responses.tar.gz")

    files = response.get("files", [])
    if not files:
        report("No se encontró diffbot_responses.tar.gz en la carpeta.")
        # TODO: Handle this possible issue 
        exit(1)
    else:
        report("Descargando diffbot_responses.tar.gz ...")
        file_info = files[0]
        request = drive_service.files().get_media(fileId=file_info["id"])
        with output_path_json.open("wb") as output_file:
            downloader = MediaIoBaseDownload(output_file, request)
            done = False
            while not done:
                _, done = downloader.next_chunk()
        report("Descargando diffbot_responses.tar.gz ... Listo")

        report("Extrayendo diffbot_responses.tar.gz ...")
        subprocess.run(['tar', '-xz', '-f', f'{download_root}/diffbot_responses.tar.gz', '-C', f'{diffbot_folder}'])
        report("Extrayendo diffbot_responses.tar.gz ... Listo")

    ws = spreadsheet.worksheet('INBOX')
    raw_values = ws.get_all_values()

    headers = ['Fecha_deteccion', 'Medio', 'Titulo', 'Link', 'Keyword_detectada',
            'Fuente', 'Revisado', 'Validado', 'Observaciones', 'Estado_IA',
            'Palabras_detectadas', 'Puntaje', 'archivo', 'Puntaje_solo_titulo', 'otro_2']

    # Map values to records (skipping row 0 if row 0 has the old headers)
    all_records = gspread.utils.to_records(headers, raw_values[1:])

    df_sd = pd.DataFrame(all_records)

    # Add column with the actual row number in the Google Spreadsheet
    # (raw_values[1:] starts at spreadsheet row 2)
    df_sd["gdrive_index"] = range(2, 2 + len(df_sd))

    # Remove invalid rows: no Title
    # Filter out empty/whitespace strings and NaNs
    col = df_sd.columns[2]
    df_sd = df_sd[df_sd[col].astype(str).str.strip().ne("") & df_sd[col].notna()]

    # Reset index, keep the old index for reference, matching the row number in the gdrive sheet.
    # df_sd.reset_index(names="gdrive_index", inplace=True)
    df_sd.reset_index(drop=True, inplace=True)

    # Remove column "Medio", it's always equal to "Google News"
    df_sd.drop(columns=["Medio"], inplace=True)

    # Remove column "Fuente", it shows the search source URL, not the url for the article
    df_sd.drop(columns=["Fuente"], inplace=True)

    # Keep only rows with .txt files in the "archivo" column
    df_sd = df_sd[df_sd["archivo"].astype(str).str.endswith(".txt")]

    report(f"SIN DETENIDOS descargada: {len(df_sd)} registros válidos")


    return df_sd