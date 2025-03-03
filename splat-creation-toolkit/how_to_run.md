# Splat Creation Toolkit Setup Guide

## Setup Instructions

### 1. Install OpenSplat on Windows
- Follow the official instructions at: https://github.com/pierotofy/OpenSplat
- **Common Issue**: If you encounter CUDA compilation problems, refer to this solution:
  https://stackoverflow.com/questions/56636714/cuda-compile-problems-on-windows-cmake-error-no-cuda-toolset-found#comment121766428_56665992

### 2. Install COLMAP on Windows
- Download and install from the official COLMAP website

## Running the Toolkit

### Step 1: Prepare Your Images
- Place all your images in the `input_images` folder

### Step 2: Generate COLMAP Model
- Run `1_run_colmap_with_input_images.py` to create the COLMAP model

### Step 3: Generate Splat
- Run `2_fun_opensplat_with_input_images.py` to create the final splat
