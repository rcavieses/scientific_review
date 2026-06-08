#!/bin/bash
# Activate virtual environment and load .env
source venv/bin/activate
export $(cat .env | grep -v '^#' | xargs)
echo "✓ Virtual environment activated"
echo "✓ Environment variables loaded from .env"
echo "✓ Ready to use the Scientific Review project"
