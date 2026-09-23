"""main/views.py"""
from django.contrib import messages
from django.shortcuts import render, redirect
from django.db.models import Q

from .models import Article
from .utils import download_data, import_articles_from_csv


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


def update_db(request):
    download_data(progress_callback=lambda message: messages.info(request, message))
    messages.success(request, 'Actualización completa.')
    return redirect('home')