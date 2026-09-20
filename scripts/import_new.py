import json
import os

import gspread


from main.models import Article


def import_articles_from_file(filepath):
    """
    Import Article objects from a text file containing JSON objects
    (one JSON object per line).

    :param filepath: Path to the text file containing JSON data.
    :return: Tuple (created_count, skipped_count, error_count)
    """
    created_count = 0
    skipped_count = 0
    error_count = 0

    if not os.path.isfile(filepath):
        raise FileNotFoundError(f"File not found: {filepath}")

    with open(filepath, "r", encoding="utf-8") as f:
        for line_number, line in enumerate(f, start=1):
            line = line.strip()
            if not line:
                continue

            try:
                data = json.loads(line)
            except json.JSONDecodeError as e:
                print(f"[Line {line_number}] Invalid JSON: {e}")
                error_count += 1
                continue

            try:
                # TODO: adjust field mapping to match Article model fields
                # e.g. title = data.get("title"), body = data.get("body"), etc.

                # TODO: check for duplicates before creating (e.g. by slug/title)
                # if Article.objects.filter(...).exists():
                #     skipped_count += 1
                #     continue

                article = Article(
                    # title=data.get("title"),
                    # content=data.get("content"),
                    # ...
                )
                article.save()
                created_count += 1

            except Exception as e:
                print(f"[Line {line_number}] Error creating Article: {e}")
                error_count += 1

    return created_count, skipped_count, error_count


def import_articles_from_directory(directory_path):
    """
    Import Article objects from all text files in a directory.

    :param directory_path: Path to directory containing JSON text files.
    """
    total_created = 0
    total_skipped = 0
    total_errors = 0

    for filename in os.listdir(directory_path):
        filepath = os.path.join(directory_path, filename)
        if not os.path.isfile(filepath):
            continue

        created, skipped, errors = import_articles_from_file(filepath)
        total_created += created
        total_skipped += skipped
        total_errors += errors

    print(
        f"Import complete: {total_created} created, "
        f"{total_skipped} skipped, {total_errors} errors."
    )


if __name__ == "__main__":
    # TODO: set the correct path to your import directory or file
    import_articles_from_directory("path/to/import/files")
