import os
import subprocess
from pathlib import Path
import shutil
from datetime import datetime

def run_command(command, cwd=None, shell=False):
    """Run a command and check for errors"""
    try:
        subprocess.run(command, check=True, cwd=cwd, shell=shell)
    except subprocess.CalledProcessError as e:
        print(f"Error running command: {' '.join(command) if isinstance(command, list) else command}")
        raise e

def setup_visual_studio_env():
    """Setup Visual Studio environment variables"""
    vs_path = r"C:\Program Files\Microsoft Visual Studio\2022\Community\VC\Auxiliary\Build\vcvars64.bat"
    if not os.path.exists(vs_path):
        raise FileNotFoundError(f"Visual Studio path not found: {vs_path}")
    
    # Call vcvars64.bat and get the environment
    run_command(vs_path, shell=True)

def run_opensplat_pipeline(
    libtorch_path=r"C:\Users\Mega-PC\Desktop\projects\map_to_3d\libtorch",
    opencv_path=r"C:\Users\Mega-PC\Desktop\projects\map_to_3d\opencv\build",
    cuda_path=r"C:\Program Files\NVIDIA GPU Computing Toolkit\CUDA\v12.5",
    dataset_path=r"C:\Users\Mega-PC\Desktop\projects\map_to_3d\dataset",
    num_points=1000
):
    """
    Run the OpenSplat pipeline
    
    Args:
        libtorch_path (str): Path to libtorch installation
        opencv_path (str): Path to OpenCV build directory
        cuda_path (str): Path to CUDA installation
        dataset_path (str): Path to the dataset
        num_points (int): Number of points to process
    """
    # Setup Visual Studio environment
    print("Setting up Visual Studio environment...")
    setup_visual_studio_env()

    # Clone OpenSplat if not exists
    opensplat_dir = Path("OpenSplat")
    if not opensplat_dir.exists():
        print("Cloning OpenSplat repository...")
        run_command(["git", "clone", "https://github.com/pierotofy/OpenSplat", "OpenSplat"])

    # Create and enter build directory
    build_dir = opensplat_dir / "build"
    build_dir.mkdir(exist_ok=True)

    # Configure CMake
    print("Configuring CMake...")
    cmake_command = [
        "cmake",
        "-DCMAKE_PREFIX_PATH=" + libtorch_path,
        f"-DOPENCV_DIR={opencv_path}",
        "-DCMAKE_BUILD_TYPE=Release",
        f'-DCMAKE_GENERATOR_TOOLSET=cuda={cuda_path}',
        ".."
    ]
    run_command(cmake_command, cwd=str(build_dir))

    # Build the project
    print("Building OpenSplat...")
    run_command(["cmake", "--build", ".", "--config", "Release"], cwd=str(build_dir))

    # Run OpenSplat
    print("Running OpenSplat...")
    release_dir = build_dir / "Release"
    run_command([
        str(release_dir / "opensplat"),
        dataset_path,
        "-n", str(num_points)
    ])

    # Copy the output splat file with timestamp
    splat_file = release_dir / "splat.ply"
    if splat_file.exists():
        # Create recent_splats directory if it doesn't exist
        recent_splats_dir = Path("recent_splats")
        recent_splats_dir.mkdir(exist_ok=True)
        
        # Generate timestamp and new filename
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        new_splat_file = recent_splats_dir / f"splat_{timestamp}.ply"
        
        # Copy the file
        shutil.copy2(splat_file, new_splat_file)
        print(f"Copied splat file to: {new_splat_file}")

if __name__ == "__main__":
    try:
        run_opensplat_pipeline()
    except Exception as e:
        print(f"Error: {e}")
        exit(1) 