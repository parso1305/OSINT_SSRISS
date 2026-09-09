from bs4 import BeautifulSoup

with open('fixture.html', 'r') as file:
    content = file.read()
    
    soup = BeautifulSoup(content, 'lxml')
    tags = soup.find_all('h2')
    
    for tag in tags:
        print(tag.text)