import os.path as osp
from glob import glob
from typing import Callable, Optional

from tqdm import tqdm

import yaml
import torch
from torch_geometric.data import Dataset
from torch_geometric.data import extract_zip
from torch_geometric.io import read_ply

class CoMA(Dataset):
    url = 'https://coma.is.tue.mpg.de/'

    categories = [
        'bareteeth', #0
        'cheeks_in', #1
        'eyebrow', #2
        'high_smile', #3
        'lips_back', #4
        'lips_up', #5
        'mouth_down', #6
        'mouth_extreme', #7
        'mouth_middle', #8
        'mouth_open', #9
        'mouth_side', #10
        'mouth_up', #11
    ]

    def __init__(self, root: str,
                 transform: Optional[Callable] = None,
                 pre_transform: Optional[Callable] = None,
                 pre_filter: Optional[Callable] = None):
        super().__init__(root, transform, pre_transform, pre_filter)

    @property
    def raw_file_names(self) -> str:
        return 'COMA_data.py'

    @property
    def processed_file_names(self):
        return ["data_{}.pt".format(str(i)) for i in range(10412)] #7725, 20465

    def download(self):
        raise RuntimeError(
            f"Dataset not found. Please download 'COMA_data.py' from "
            f"'{self.url}' and move it to '{self.raw_dir}'")

    def load_yaml(self):
        with open('/home/brenda/Documents/master/thesis/IAS_gutierrez_2022/data/dataset_definition.yaml', 'r') as file:
            try:
                return yaml.safe_load(file)
            except yaml.YAMLError as exc:
                print(exc)

    def process(self):
        folders = sorted(glob(osp.join(self.raw_dir, 'FaceTalk_*')))
        if len(folders) == 0:
            extract_zip(self.raw_paths[0], self.raw_dir, log=False)
            folders = sorted(glob(osp.join(self.raw_dir, 'FaceTalk_*')))

        indx = 0 #20465
        indx_no_filter = -1


        dataset_indices = self.load_yaml()
        for folder_idx, folder in tqdm(enumerate(folders), desc="Loading dataset..."): #tqdm(folders, desc="Loading dataset..."):
            for i, category in enumerate(self.categories):
                files = sorted(glob(osp.join(folder, category, '*.ply')))

                if isinstance(dataset_indices[folder_idx][category.upper()][0], list) == False:
                    initial = dataset_indices[folder_idx][category.upper()][0]
                    final = dataset_indices[folder_idx][category.upper()][1]
                    double_index = False
                else:
                    initial = dataset_indices[folder_idx][category.upper()][0][0]
                    final = dataset_indices[folder_idx][category.upper()][0][1]

                    initial_der = dataset_indices[folder_idx][category.upper()][1][0]
                    final_der = dataset_indices[folder_idx][category.upper()][1][1]
                    double_index = True

                for j, f in enumerate(files):
                    indx_no_filter += 1

                    if initial == -1:
                        continue

                    if indx_no_filter < initial or indx_no_filter > final:
                        if double_index:
                            if indx_no_filter < initial_der or indx_no_filter > final_der:
                                continue
                        else:
                            continue

                    #print(indx_no_filter)


                    #if double_index:
                    #    if indx_no_filter < initial or indx_no_filter > final:
                    #        if indx_no_filter < initial_der or indx_no_filter > final_der:
                    #            continue
                    #else:
                    #    if indx_no_filter < initial or indx_no_filter > final:
                    #        continue

                    data = read_ply(f)
                    data.y = torch.tensor([i], dtype=torch.long)
                    if self.pre_filter is not None and \
                            not self.pre_filter(data):
                        continue
                    if self.pre_transform is not None:
                        data = self.pre_transform(data)
                    self.reduce_faces(data)
                    torch.save(data, osp.join(self.processed_dir, f'data_{indx}.pt'))
                    indx += 1
        print("{} graphs have been processed!".format(indx))

    def reduce_faces(self, data):
        n1, n2, n3 = [], [], []
        new_indices = {}
        new_pos = []
        idx = 0
        for p, u in zip(data.pos, range(len(data.pos))):
            if p[2] > 0.01:
                new_indices[u] = idx
                new_pos.append(p)
                idx += 1
        for p1, p2, p3 in zip(data.face[0], data.face[1], data.face[2]):
            if data.pos[p1][2] > 0.01 and data.pos[p2][2] > 0.01 and data.pos[p3][2] > 0.01:
                n1.append(new_indices[int(p1)])
                n2.append(new_indices[int(p2)])
                n3.append(new_indices[int(p2)])
        data.face = torch.stack((torch.tensor(n1, dtype=torch.long), torch.tensor(n2, dtype=torch.long), torch.tensor(n3, dtype=torch.long)))
        data.pos = torch.stack(new_pos)

    def reduce_graph(self, data):
        edge1, edge2 = [], []
        new_indices = {}
        new_pos = []
        idx = 0
        for p, u in zip(data.pos, range(len(data.pos))):
            if p[2] > 0.01:
                new_indices[u] = idx
                new_pos.append(p)
                idx += 1
        for e1, e2 in zip(data.edge_index[0], data.edge_index[1]):
            if data.pos[e1][2] > 0.01 and data.pos[e2][2] > 0.01:
                edge1.append(new_indices[int(e1)])
                edge2.append(new_indices[int(e2)])
        data.edge_index = torch.stack((torch.tensor(edge1, dtype=torch.long), torch.tensor(edge2, dtype=torch.long)))
        data.pos = torch.stack(new_pos)

    def len(self):
        return len(self.processed_file_names)

    def get(self, idx):
        data = torch.load(osp.join(self.processed_dir, f'data_{idx}.pt'))
        return data