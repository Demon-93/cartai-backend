import os
import requests
from bs4 import BeautifulSoup
from typing import Dict, List, Optional
import re


def extract_price(price_text: str) -> Optional[float]:
    """Extract numeric price from text."""
    if not price_text:
        return None
    # Remove currency symbols, commas, and spaces
    cleaned = re.sub(r'[^\d.]', '', price_text)
    try:
        return float(cleaned)
    except (ValueError, TypeError):
        return None


def extract_rating(rating_text: str) -> Optional[float]:
    """Extract numeric rating from text."""
    if not rating_text:
        return None
    # Extract first number (rating out of 5)
    match = re.search(r'(\d+(?:\.\d+)?)', rating_text)
    if match:
        try:
            return float(match.group(1))
        except ValueError:
            return None
    return None


def extract_reviews(review_text: str) -> Optional[int]:
    """Extract number of reviews from text."""
    if not review_text:
        return None
    # Extract number, handle commas and "reviews"/"ratings" text
    match = re.search(r'([\d,]+)', review_text.replace(',', ''))
    if match:
        try:
            return int(match.group(1).replace(',', ''))
        except ValueError:
            return None
    return None


def parse_flipkart(soup: BeautifulSoup) -> List[dict]:
    """Parse Flipkart search results."""
    products = []

    # Flipkart product selectors (may need updating)
    product_cards = soup.find_all('div', {'class': '_2kHMtA'}) or soup.find_all('div', {'data-id': True})

    for card in product_cards[:5]:  # Limit to top 5
        try:
            # Title
            title_elem = card.find('div', {'class': '_4rR01T'}) or card.find('a', {'class': 's1Q9rs'})
            title = title_elem.get_text(strip=True) if title_elem else None

            # Price
            price_elem = card.find('div', {'class': '_30jeq3'}) or card.find('div', {'class': '_1_WHN1'})
            price = extract_price(price_elem.get_text(strip=True)) if price_elem else None

            # Rating
            rating_elem = card.find('div', {'class': 'gUuXy-'}) or card.find('div', {'class': '_3LWZlK'})
            rating = extract_rating(rating_elem.get_text(strip=True)) if rating_elem else None

            # Reviews
            reviews_elem = card.find('span', {'class': '_2_R_DZ'}) or card.find('span', {'class': '_1TPvTK'})
            reviews = extract_reviews(reviews_elem.get_text(strip=True)) if reviews_elem else None

            # Product Link - clean version
            link = None
            link_elem = card.find('a', href=True)
            if link_elem:
                link_href = link_elem.get('href')
                if link_href:
                    # Clean the link: remove any tracking parameters, keep only the path
                    if link_href.startswith('http'):
                        # Already absolute, but clean tracking params
                        link = link_href.split('?')[0].split('#')[0]
                    elif link_href.startswith('/'):
                        # Relative path, prepend base
                        link = f"https://www.flipkart.com{link_href.split('?')[0].split('#')[0]}"

            if title and price:
                products.append({
                    'title': title,
                    'price': price,
                    'rating': rating,
                    'reviews': reviews,
                    'link': link
                })
        except Exception as e:
            print(f"Error parsing Flipkart product: {e}")
            continue

    return products


def parse_amazon(soup: BeautifulSoup) -> List[dict]:
    """Parse Amazon search results."""
    products = []

    # Amazon product selectors
    product_cards = soup.find_all('div', {'data-component-type': 's-search-result'})

    for card in product_cards[:5]:  # Limit to top 5
        try:
            # Title
            title_elem = card.find('h2') or card.find('span', {'class': 'a-size-medium'})
            title = title_elem.get_text(strip=True) if title_elem else None

            # Price
            price_elem = card.find('span', {'class': 'a-price-whole'})
            price_frac = card.find('span', {'class': 'a-price-fraction'})
            if price_elem:
                price_text = price_elem.get_text(strip=True)
                if price_frac:
                    price_text += '.' + price_frac.get_text(strip=True)
                price = extract_price(price_text)
            else:
                price = None

            # Rating
            rating_elem = card.find('span', {'class': 'a-icon-alt'})
            rating = extract_rating(rating_elem.get_text(strip=True)) if rating_elem else None

            # Reviews
            reviews_elem = card.find('span', {'class': 'a-size-base'})
            reviews = extract_reviews(reviews_elem.get_text(strip=True)) if reviews_elem else None

            # Product Link - clean version (from h2 anchor)
            link = None
            h2_elem = card.find('h2')
            if h2_elem:
                link_elem = h2_elem.find('a', href=True)
                if link_elem:
                    link_href = link_elem.get('href')
                    if link_href:
                        # Clean the link: remove tracking parameters
                        if link_href.startswith('http'):
                            link = link_href.split('?')[0].split('#')[0]
                        elif link_href.startswith('/'):
                            link = f"https://www.amazon.in{link_href.split('?')[0].split('#')[0]}"

            if title and price:
                products.append({
                    'title': title,
                    'price': price,
                    'rating': rating,
                    'reviews': reviews,
                    'link': link
                })
        except Exception as e:
            print(f"Error parsing Amazon product: {e}")
            continue

    return products


def search_products(query: str) -> Dict[str, List[dict]]:
    """
    Search products on Flipkart and Amazon using ScraperAPI.
    Returns dict with 'flipkart' and 'amazon' keys containing product lists.
    """
    scraper_api_key = os.environ.get("SCRAPER_API_KEY")
    if not scraper_api_key:
        raise ValueError("SCRAPER_API_KEY environment variable not set")

    scraper_url = "http://api.scraperapi.com"

    flipkart_url = f"https://www.flipkart.com/search?q={query}"
    amazon_url = f"https://www.amazon.in/s?k={query}"

    results = {
        "flipkart": [],
        "amazon": []
    }

    # Fetch Flipkart
    try:
        flipkart_response = requests.get(
            scraper_url,
            params={
                "api_key": scraper_api_key,
                "url": flipkart_url,
                "autoparse": False
            },
            timeout=30
        )
        if flipkart_response.status_code == 200:
            soup = BeautifulSoup(flipkart_response.text, 'html.parser')
            results["flipkart"] = parse_flipkart(soup)
    except Exception as e:
        print(f"Error scraping Flipkart: {e}")

    # Fetch Amazon
    try:
        amazon_response = requests.get(
            scraper_url,
            params={
                "api_key": scraper_api_key,
                "url": amazon_url,
                "autoparse": False
            },
            timeout=30
        )
        if amazon_response.status_code == 200:
            soup = BeautifulSoup(amazon_response.text, 'html.parser')
            results["amazon"] = parse_amazon(soup)
    except Exception as e:
        print(f"Error scraping Amazon: {e}")

    return results
