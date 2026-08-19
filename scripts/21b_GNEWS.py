import pandas as pd
from gnews import GNews
gn = GNews()

gn.country = 'AR'  # News from a specific country 
gn.language = 'es'  # News in a specific language


gn.start_date = (2023, 7, 12)
gn.end_date = (2023, 7, 14)

articles = gn.get_news('Mapa de la Policía')
print(len(articles))
print('')

for a in articles:
    print(a['title'])
    print(a['published date'])
    print(a['description'])
    print(a['url'])
    print('---')