git clone --recursive -b dev https://github.com/camenduru/ges-splatting ges
conda activate gaussian_env

pip install -q ges/submodules/diff-gaussian-rasterization


pip install -q ges/submodules/simple-knn 

pip install -q plyfile trimesh einops wandb

cd ges 