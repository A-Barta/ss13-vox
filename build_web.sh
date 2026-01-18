#!/usr/bin/env bash
# Build script for web UI (CoffeeScript + SCSS)
# Replaces the old BUILD.py that used pybuildtools

set -e

NODE_BIN="node_modules/.bin"
DIST_HTML="dist/html"

# Install dependencies if needed
if [ ! -d "node_modules" ]; then
    echo "Installing dependencies..."
    yarn install
fi

# Create output directories
mkdir -p "$DIST_HTML/browser"

# Compile CoffeeScript with Babel transpilation
echo "Compiling CoffeeScript..."
"$NODE_BIN/coffee" --transpile -o "$DIST_HTML" coffee/aivoice.coffee

# Minify JavaScript
echo "Minifying JavaScript..."
"$NODE_BIN/uglifyjs" "$DIST_HTML/aivoice.js" -o "$DIST_HTML/aivoice.min.js"

# Compile SCSS
echo "Compiling SCSS..."
"$NODE_BIN/sass" scss/style.scss "$DIST_HTML/browser/aivoice.css"

echo "Web build complete."
