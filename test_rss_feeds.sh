#!/bin/bash

# Script to test RSS feeds and check if they have images/content
# Usage: ./test_rss_feeds.sh

echo "Testing RSS Feeds for Images and Content..."
echo "=============================================="
echo ""

# Color codes
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

test_feed() {
    local name="$1"
    local url="$2"

    echo -e "${YELLOW}Testing: $name${NC}"
    echo "URL: $url"

    # Fetch the RSS feed
    response=$(curl -s -L --max-time 10 "$url" 2>&1)

    if [ $? -ne 0 ]; then
        echo -e "${RED}✗ Failed to fetch feed${NC}"
        echo ""
        return
    fi

    # Check if it's valid XML/RSS
    if ! echo "$response" | grep -q "<rss\|<feed"; then
        echo -e "${RED}✗ Not a valid RSS/Atom feed${NC}"
        echo ""
        return
    fi

    # Check for images in various formats
    has_media_thumbnail=$(echo "$response" | grep -c "<media:thumbnail")
    has_media_content=$(echo "$response" | grep -c "<media:content")
    has_enclosure=$(echo "$response" | grep -c "<enclosure.*image")
    has_img_tag=$(echo "$response" | grep -c "<img")
    has_content=$(echo "$response" | grep -c "<content")

    # Count items
    item_count=$(echo "$response" | grep -c "<item>\|<entry>")

    echo "Items found: $item_count"

    if [ $has_media_thumbnail -gt 0 ]; then
        echo -e "${GREEN}✓ Has media:thumbnail ($has_media_thumbnail)${NC}"
    fi

    if [ $has_media_content -gt 0 ]; then
        echo -e "${GREEN}✓ Has media:content ($has_media_content)${NC}"
    fi

    if [ $has_enclosure -gt 0 ]; then
        echo -e "${GREEN}✓ Has image enclosures ($has_enclosure)${NC}"
    fi

    if [ $has_img_tag -gt 0 ]; then
        echo -e "${GREEN}✓ Has <img> tags ($has_img_tag)${NC}"
    fi

    if [ $has_content -gt 0 ]; then
        echo -e "${GREEN}✓ Has <content> field ($has_content)${NC}"
    fi

    # Show first item title as sample
    first_title=$(echo "$response" | grep -m 1 "<title>" | sed 's/<[^>]*>//g' | sed 's/^[[:space:]]*//')
    if [ ! -z "$first_title" ]; then
        echo "Sample title: $first_title"
    fi

    # Overall assessment
    total_image_tags=$((has_media_thumbnail + has_media_content + has_enclosure + has_img_tag + has_content))

    if [ $total_image_tags -eq 0 ]; then
        echo -e "${RED}⚠ NO IMAGE SOURCES FOUND - Will need OG fallback${NC}"
    else
        echo -e "${GREEN}✓ Feed has image sources${NC}"
    fi

    echo ""
}

# Test new crypto feeds
echo "=== CRYPTO & FINANCE ==="
test_feed "CoinDesk" "https://www.coindesk.com/arc/outboundfeeds/rss/"
test_feed "Cointelegraph" "https://cointelegraph.com/rss"
test_feed "The Block" "https://www.theblock.co/rss.xml"
test_feed "Decrypt" "https://decrypt.co/feed"

echo "=== GAMING ==="
test_feed "GameSpot" "https://www.gamespot.com/feeds/news/"
test_feed "VG247" "https://www.vg247.com/feed/"
test_feed "IGN" "https://feeds.ign.com/ign/all"
test_feed "Eurogamer" "https://www.eurogamer.net/?format=rss"

echo "=== TECHNOLOGY ==="
test_feed "Ars Technica" "https://feeds.arstechnica.com/arstechnica/index"
test_feed "Engadget" "https://www.engadget.com/rss.xml"
test_feed "The Next Web" "https://feeds.feedburner.com/thenextweb"

echo "=== CLIMATE & SCIENCE ==="
test_feed "NASA Earth" "https://www.nasa.gov/rss/dyn/earth.rss"
test_feed "Scientific American" "https://www.scientificamerican.com/feed/"

echo "=== CURRENT FEEDS (Check Status) ==="
test_feed "TechCrunch" "https://techcrunch.com/feed/"
test_feed "The Verge" "https://www.theverge.com/rss/index.xml"
test_feed "CNBC" "https://search.cnbc.com/rs/search/combinedcms/view.xml?partnerId=wrss01&id=10001147"
test_feed "Forbes Business" "https://www.forbes.com/business/feed/"

echo "=============================================="
echo "Testing complete!"
echo ""
echo "Legend:"
echo "✓ = Feed has images built-in"
echo "⚠ = Feed needs Open Graph fallback"
