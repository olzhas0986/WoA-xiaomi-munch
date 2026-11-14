"""Position-independent reads for image files also inspected with SEEK_DATA."""
import os

def read_image_range(fd,offset,size):
    if offset<0 or size<0:raise ValueError('Negative image range')
    data=os.pread(fd,size,offset)
    if len(data)!=size:raise ValueError(f'Short image read at {offset}: {len(data)} != {size}')
    return data
