# Rig 2D vektor sederhana (gaya bulat-hitam) untuk pose karakter. Render PIL, supersample.
import math
from PIL import Image, ImageDraw
OL=(22,22,28); SK=(255,255,255); SS=4
class C:
    def __init__(s,W=400,H=420):
        s.W,s.H=W,H;s.im=Image.new('RGBA',(W*SS,H*SS),(0,0,0,0));s.d=ImageDraw.Draw(s.im)
    def P(s,p):return (p[0]*SS,p[1]*SS)
    def circ(s,c,r,fill,ow=6):
        x,y=s.P(c);R=r*SS;s.d.ellipse((x-R-ow*SS,y-R-ow*SS,x+R+ow*SS,y+R+ow*SS),fill=OL);s.d.ellipse((x-R,y-R,x+R,y+R),fill=fill)
    def ell(s,c,rx,ry,fill,ow=6):
        x,y=s.P(c);s.d.ellipse((x-(rx+ow)*SS,y-(ry+ow)*SS,x+(rx+ow)*SS,y+(ry+ow)*SS),fill=OL);s.d.ellipse((x-rx*SS,y-ry*SS,x+rx*SS,y+ry*SS),fill=fill)
    def poly(s,pts,fill,ow=6):
        q=[s.P(p) for p in pts];s.d.polygon(q,fill=fill)
        for i in range(len(q)):
            a,b=q[i],q[(i+1)%len(q)];s.d.line([a,b],fill=OL,width=ow*SS);s.d.ellipse((a[0]-ow*SS/2,a[1]-ow*SS/2,a[0]+ow*SS/2,a[1]+ow*SS/2),fill=OL)
    def limb(s,pts,w,fill,ow=6):
        q=[s.P(p) for p in pts]
        for ww,col in((w+2*ow,OL),(w,fill)):
            s.d.line(q,fill=col,width=int(ww*SS),joint='curve')
            for a in(q[0],q[-1]):s.d.ellipse((a[0]-ww*SS/2,a[1]-ww*SS/2,a[0]+ww*SS/2,a[1]+ww*SS/2),fill=col)
            for a in q[1:-1]:s.d.ellipse((a[0]-ww*SS/2,a[1]-ww*SS/2,a[0]+ww*SS/2,a[1]+ww*SS/2),fill=col)
    def line(s,pts,w,col=OL):
        q=[s.P(p) for p in pts];s.d.line(q,fill=col,width=int(w*SS),joint='curve')
        for a in(q[0],q[-1]):s.d.ellipse((a[0]-w*SS/2,a[1]-w*SS/2,a[0]+w*SS/2,a[1]+w*SS/2),fill=col)
    def dot(s,c,r,col=OL):
        x,y=s.P(c);R=r*SS;s.d.ellipse((x-R,y-R,x+R,y+R),fill=col)
    def arc(s,box,a0,a1,w,col=OL):
        x0,y0,x1,y1=box;s.d.arc((x0*SS,y0*SS,x1*SS,y1*SS),a0,a1,fill=col,width=int(w*SS))
    def out(s):return s.im.resize((s.W,s.H),Image.LANCZOS)
def dirv(th,side=1,L=1):  # sudut dari "lurus ke bawah"; positif = menjauhi badan (depan) / maju (samping)
    t=math.radians(th);return (math.sin(t)*side*L,math.cos(t)*L)
def arm(c,sh,side,t1,t2,L1,L2,w,sleeve,hand=True,skin=SK):
    e=(sh[0]+dirv(t1,side,L1)[0],sh[1]+dirv(t1,side,L1)[1]);h=(e[0]+dirv(t1+t2,side,L2)[0],e[1]+dirv(t1+t2,side,L2)[1])
    c.limb([sh,e],w,sleeve);c.limb([e,h],w*.78,skin)
    if hand:c.circ(h,w*.62,skin,5)
    return e,h
def face_front(c,ctr,r,mood='n',mouth=0):
    x,y=ctr;c.dot((x-r*.33,y-r*.05),5);c.dot((x+r*.33,y-r*.05),5)
    if mood=='surp':c.ell((x,y+r*.42),7,9,OL,0)
    elif mouth:c.ell((x,y+r*.4),9,6+mouth*3,OL,0)
    else:c.arc((x-r*.3,y+r*.12,x+r*.3,y+r*.5),20,160,4)
def face_side(c,ctr,r,mouth=0):
    x,y=ctr;c.dot((x+r*.42,y-r*.05),5)
    if mouth:c.ell((x+r*.5,y+r*.42),7,4+mouth*3,OL,0)
    else:c.arc((x+r*.15,y+r*.15,x+r*.7,y+r*.5),20,150,4)
