// Read-only libntfs-3g adapter. The caller supplies bounded raw reads (e.g. ADB).
#define _GNU_SOURCE
#include <stdint.h>
#include <time.h>
#include <stdarg.h>
#include <stdlib.h>
#include <string.h>
#include <errno.h>
#include <fcntl.h>
#include <unistd.h>
#include <sys/stat.h>
#include <linux/fs.h>
#include <ntfs-3g/device.h>
#include <ntfs-3g/volume.h>
#include <ntfs-3g/inode.h>
#include <ntfs-3g/attrib.h>
#include <ntfs-3g/dir.h>
typedef int64_t (*fetch_fn)(int64_t, int64_t, void *);
struct backend { fetch_fn fetch;int64_t size,pos; };
struct handle { ntfs_volume *vol;struct backend *backend; };
struct file { ntfs_inode *inode;ntfs_attr *attr;ntfs_volume *vol; };
static int open_ro(struct ntfs_device *d,int flags){
 if((flags&O_ACCMODE)!=O_RDONLY){errno=EROFS;return -1;}
 NDevSetOpen(d);NDevSetReadOnly(d);return 0;
}
static int close_ro(struct ntfs_device *d){NDevClearOpen(d);return 0;}
static s64 seek_ro(struct ntfs_device *d,s64 off,int whence){
 struct backend *b=d->d_private;int64_t base=whence==SEEK_SET?0:whence==SEEK_CUR?b->pos:whence==SEEK_END?b->size:-1;
 if(base<0 || off < -base || off>b->size-base){errno=EINVAL;return -1;}
 return b->pos=base+off;
}
static s64 pread_ro(struct ntfs_device *d,void *out,s64 count,s64 offset){
 struct backend *b=d->d_private;
 if(offset<0 || count<0 || offset>b->size){errno=EINVAL;return -1;}
 if(count>b->size-offset)count=b->size-offset;
 s64 n=b->fetch(offset,count,out);if(n<0)errno=EIO;return n;
}
static s64 read_ro(struct ntfs_device *d,void *out,s64 n){struct backend *b=d->d_private;s64 got=pread_ro(d,out,n,b->pos);if(got>0)b->pos+=got;return got;}
static s64 write_ro(struct ntfs_device *d,const void *p,s64 n){(void)d;(void)p;(void)n;errno=EROFS;return -1;}
static s64 pwrite_ro(struct ntfs_device *d,const void *p,s64 n,s64 off){(void)off;return write_ro(d,p,n);}
static int sync_ro(struct ntfs_device *d){(void)d;return 0;}
static int stat_ro(struct ntfs_device *d,struct stat *s){struct backend *b=d->d_private;memset(s,0,sizeof *s);s->st_mode=S_IFREG|0400;s->st_size=b->size;s->st_blksize=4096;s->st_nlink=1;return 0;}
static int ioctl_ro(struct ntfs_device *d,unsigned long cmd,void *arg){
 struct backend *b=d->d_private;
 if(cmd==BLKGETSIZE64){*(uint64_t *)arg=b->size;return 0;}
 if(cmd==BLKSSZGET){*(int *)arg=4096;return 0;}
 if(cmd==BLKGETSIZE){*(unsigned long *)arg=b->size/512;return 0;}
 errno=ENOTTY;return -1;
}
static struct ntfs_device_operations ops={open_ro,close_ro,seek_ro,read_ro,write_ro,pread_ro,pwrite_ro,sync_ro,stat_ro,ioctl_ro};
void *bridge_open(int64_t size,fetch_fn fetch){
 struct handle *h=calloc(1,sizeof *h);if(!h)return NULL;
 h->backend=calloc(1,sizeof *h->backend);if(!h->backend){free(h);return NULL;}
 h->backend->fetch=fetch;h->backend->size=size;
 struct ntfs_device *d=ntfs_device_alloc("read-only-adb",0,&ops,h->backend);
 if(!d){free(h->backend);free(h);return NULL;}
 h->vol=ntfs_device_mount(d,NTFS_MNT_RDONLY|NTFS_MNT_FORENSIC|NTFS_MNT_IGNORE_HIBERFILE);
 if(!h->vol){ntfs_device_free(d);free(h->backend);free(h);return NULL;}
 return h;
}
void bridge_close(void *p){struct handle *h=p;if(!h)return;ntfs_umount(h->vol,1);free(h->backend);free(h);}
void *bridge_file_open(void *p,const char *path,int64_t *size){
 struct handle *h=p;struct file *f=calloc(1,sizeof *f);if(!f)return NULL;
 f->vol=h->vol;
 f->inode=ntfs_pathname_to_inode(h->vol,NULL,path);if(!f->inode){free(f);return NULL;}
 f->attr=ntfs_attr_open(f->inode,AT_DATA,AT_UNNAMED,0);
 if(!f->attr){ntfs_inode_close(f->inode);free(f);return NULL;}
 *size=f->attr->data_size;return f;
}
int64_t bridge_file_read(void *p,int64_t off,int64_t size,void *buffer){struct file *f=p;return ntfs_attr_pread(f->attr,off,size,buffer);}
int64_t bridge_file_map(void *p,int64_t off){
 struct file *f=p;
 if(off<0 || off>=f->attr->data_size || !NAttrNonResident(f->attr) || f->attr->data_flags){errno=EOPNOTSUPP;return -1;}
 int64_t cluster=f->vol->cluster_size;
 LCN lcn=ntfs_attr_vcn_to_lcn(f->attr,off/cluster);
 if(lcn<0){errno=EIO;return -1;}
 return lcn*cluster+off%cluster;
}
void bridge_file_close(void *p){struct file *f=p;if(f){ntfs_attr_close(f->attr);ntfs_inode_close(f->inode);free(f);}}
typedef void (*entry_fn)(const void *,int,unsigned);
static int entry(void *p,const ntfschar *name,int len,int kind,s64 pos,MFT_REF ref,unsigned type){(void)pos;(void)ref;if(kind!=2)((entry_fn)p)(name,len,type);return 0;}
int bridge_list(void *p,const char *path,entry_fn emit){
 struct handle *h=p;ntfs_inode *n=ntfs_pathname_to_inode(h->vol,NULL,path);if(!n)return -1;
 s64 pos=0;int status=ntfs_readdir(n,&pos,(void *)emit,entry);ntfs_inode_close(n);return status;
}
