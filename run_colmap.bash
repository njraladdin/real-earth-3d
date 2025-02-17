#!/bin/bash
# COLMAP SfM Pipeline Bash Script
# This script assumes you have a dataset folder with an "images" subfolder.
# It performs feature extraction, matching, sparse reconstruction,
# and converts the output model to a TXT format.
#
# Make sure COLMAP is installed and accessible in your system's PATH.
# Adjust the "dataset" path if your directory structure differs.

# Exit immediately if a command exits with a non-zero status.
set -e

# Check if the images directory exists
if [ ! -d "dataset/images" ]; then
    echo "Error: dataset/images folder not found!"
    exit 1
fi

# Delete existing sparse directory and database if they exist
echo "Cleaning up existing files..."
rm -rf dataset/sparse
rm -f dataset/database.db

echo "Starting COLMAP pipeline..."

# Step 1: Feature Extraction
echo "Step 1: Extracting features..."
colmap feature_extractor \
    --database_path dataset/database.db \
    --image_path dataset/images 


# Step 2: Feature Matching
echo "Step 2: Matching features..."
colmap exhaustive_matcher \
    --database_path dataset/database.db

# Step 3: Create output folder for sparse reconstruction
echo "Step 3: Creating sparse reconstruction folder..."
mkdir -p dataset/sparse

# Step 4: Sparse Reconstruction (Mapper)
echo "Step 4: Running mapper for sparse reconstruction..."
colmap mapper \
    --database_path dataset/database.db \
    --image_path dataset/images \
    --output_path dataset/sparse

# Step 5: Convert the model to TXT format
echo "Step 5: Converting model to TXT format..."
colmap model_converter \
    --input_path dataset/sparse/0 \
    --output_path dataset/sparse \
    --output_type TXT

echo "COLMAP pipeline completed successfully!"
