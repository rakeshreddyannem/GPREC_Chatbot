#!/usr/bin/env bash
# make_deploy_bundle.sh: Assembles a clean, standalone deployment bundle for Hugging Face Spaces
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "$SCRIPT_DIR/../.." && pwd)"
DEST_DIR="${1:-$ROOT_DIR/deploy/bundle}"

echo "=========================================================="
echo " Packaging GPREC Assistant Deployment Bundle"
echo " Source: $ROOT_DIR"
echo " Destination: $DEST_DIR"
echo "=========================================================="

# Clean and create target folder
rm -rf "$DEST_DIR"
mkdir -p "$DEST_DIR"

# 1. Copy core app code and config
echo "[1/6] Copying app scripts and configs..."
cp "$ROOT_DIR/app.py" "$DEST_DIR/"
cp "$ROOT_DIR/config.py" "$DEST_DIR/"
cp "$ROOT_DIR/requirements.txt" "$DEST_DIR/"
[ -f "$ROOT_DIR/requirements-dev.txt" ] && cp "$ROOT_DIR/requirements-dev.txt" "$DEST_DIR/"
cp "$ROOT_DIR/Dockerfile" "$DEST_DIR/"
cp "$ROOT_DIR/.dockerignore" "$DEST_DIR/"
cp "$ROOT_DIR/.gitattributes" "$DEST_DIR/"
cp "$ROOT_DIR/README.md" "$DEST_DIR/"
cp "$ROOT_DIR/gprec_logo1.png" "$DEST_DIR/"

# 2. Copy source packages and UI
echo "[2/6] Copying src/ and ui/ modules..."
mkdir -p "$DEST_DIR/src"
cp -r "$ROOT_DIR/src/"* "$DEST_DIR/src/"
rm -rf "$DEST_DIR/src/__pycache__"

mkdir -p "$DEST_DIR/ui"
cp -r "$ROOT_DIR/ui/"* "$DEST_DIR/ui/"
rm -rf "$DEST_DIR/ui/__pycache__"

# 3. Copy Streamlit configuration
echo "[3/6] Copying .streamlit/ config..."
mkdir -p "$DEST_DIR/.streamlit"
cp -r "$ROOT_DIR/.streamlit/"* "$DEST_DIR/.streamlit/"

# 4. Copy database
echo "[4/6] Copying database (gprec_knowledge.db)..."
if [ ! -f "$ROOT_DIR/gprec_knowledge.db" ]; then
    echo "ERROR: gprec_knowledge.db not found at $ROOT_DIR/gprec_knowledge.db" >&2
    exit 1
fi
cp "$ROOT_DIR/gprec_knowledge.db" "$DEST_DIR/"

# 5. Copy vector store
echo "[5/6] Copying vectorstore/ (FAISS index and metadata)..."
if [ ! -d "$ROOT_DIR/vectorstore" ]; then
    echo "ERROR: vectorstore directory not found at $ROOT_DIR/vectorstore" >&2
    exit 1
fi
mkdir -p "$DEST_DIR/vectorstore"
cp -r "$ROOT_DIR/vectorstore/"* "$DEST_DIR/vectorstore/"

# 6. Copy faculty photos
echo "[6/6] Copying data/faculty_photos/..."
mkdir -p "$DEST_DIR/data/faculty_photos"
if [ -d "$ROOT_DIR/data/faculty_photos" ]; then
    cp -r "$ROOT_DIR/data/faculty_photos/"* "$DEST_DIR/data/faculty_photos/"
fi

echo "=========================================================="
echo " Bundle creation completed successfully!"
echo " Location: $DEST_DIR"
echo " Total files: $(find "$DEST_DIR" -type f | wc -l)"
echo " Total size:  $(du -sh "$DEST_DIR" | cut -f1)"
echo "=========================================================="
