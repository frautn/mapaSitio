"""main/views.py"""
import csv
import sys
from datetime import datetime
import json

from django.contrib import messages
from django.shortcuts import render, redirect
from django.utils import timezone
from django.db.models import Q

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

def home(request):
    return render(request, 'main/home.html')


def articles(request):
    articles_qs = Article.objects.select_related('content').order_by('ID')
    search_query = (request.GET.get('q') or '').strip()
    validado_filter = (request.GET.get('validado') or '').strip()

    validado_values = {choice[0] for choice in Article.VALIDADO_CHOICES}
    if validado_filter and validado_filter in validado_values:
        articles_qs = articles_qs.filter(validado=validado_filter)
    else:
        validado_filter = ''

    if search_query:
        articles_qs = articles_qs.filter(
            Q(ID__icontains=search_query) | Q(GNews_title__icontains=search_query)
        )

    selected_article_id = request.GET.get('article_id')

    selected_article = None
    if selected_article_id:
        selected_article = articles_qs.filter(ID=selected_article_id).first()
    if selected_article is None:
        selected_article = articles_qs.first()

    selected_html_content = ''
    if selected_article and hasattr(selected_article, 'content'):
        selected_html_content = selected_article.content.html_content

    context = {
        'articles': articles_qs,
        'selected_article': selected_article,
        'selected_html_content': selected_html_content,
        'search_query': search_query,
        'validado_filter': validado_filter,
        'validado_choices': Article.VALIDADO_CHOICES,
    }
    return render(request, 'main/articles.html', context)


def import_export(request):
    if request.method == 'POST':
        uploaded_file = request.FILES.get('csv_file')

        if not uploaded_file:
            messages.error(request, 'Seleccioná un archivo CSV para importar.')
            return redirect('import_export')

        imported_count, updated_count, skipped_count = import_articles_from_csv(uploaded_file)
        messages.success(
            request,
            f'Importación completada: {imported_count} nuevos, {updated_count} actualizados y {skipped_count} omitidos.',
        )
        return redirect('import_export')

    return render(request, 'main/import_export.html')