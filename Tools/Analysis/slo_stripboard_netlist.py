L='ABCDEFGHIJKLMNOPQRSTU'
cuts={'A':[3,10,15,24],'B':[15,21],'C':[15],'D':[15,20],'E':[9,15],'F':[8,12,22],'G':[8,12],
'H':[8,18],'I':[6,12,18,21],'J':[6,12,18],'K':[12,18],'L':[18,22],'M':[],'N':[4,22],'O':[4,12,17],
'P':[5,12],'Q':[5,12],'R':[12],'S':[10,15,17],'T':[12,15,17],'U':[9,14,17]}
par={}
def f(x):
    while par.setdefault(x,x)!=x: x=par[x]
    return x
def u(a,b): par[f(a)]=f(b)
def h(s): return (s[0],int(s[1:]))
for r in L:
    for c in range(1,26):
        if c in cuts[r] or c+1 in cuts[r]: continue
        u((r,c),(r,c+1))
links=['A8-E8','F9-G9','H9-M9','H3-L3','I4-J4','L4-Q4','M5-U5','N2-O2','P2-U2','D11-H11','E12-N12','F13-I13',
'I11-J11','K11-O11','M14-T14','L15-U15','N17-R17','I19-N19','H21-L21','K22-Q22','C24-F24','M24-N24']
for l in links:
    a,b=l.split('-'); r1,c1=h(a); r2,c2=h(b)
    u((r1,c1),(r2,c2))
comps=[('R4k7a','A2','D2'),('C100p_a','E2','F2'),('C1n_a','G2','I2'),('R6k8','B4','F4'),('R1M_a','A5','F5'),
('D1_k','C6',None),('D1_a','F6',None),('D2_a','A7',None),('D2_k','C7',None),('C22n_a','A9','A11'),('C1u_a+','B10','D10'),
('R330k','A12','D12'),('C100n_a','D13','E13'),('R220k','A14','K14'),('R1k_a','B16','H16'),('R470k_b','F15','J15'),
('R47k','A17','F17'),('C22n_b(TS)','A18','C18'),('C1n_b','D18','F18'),('C22n_c','B20','B22'),('C22n_d','A23','A25'),
('R10k_a','D19','D22'),('C470p','E20','F20'),('R10k_b','B23','I23'),('R1M_b','D25','H25'),('R33k_a','H17','H20'),
('R22k_a','G22','J22'),('C22n_e','J23','L23'),('R33k_b','J24','L24'),('C1u_b-','I25','J25'),('R10k_c','L25','Q25'),
('R4k7b','M18','Q18'),('C100n_b','O19','Q19'),('R220','M21','S21'),('R1k_b','N23','U23'),('RCLR','P24','T24'),
('D3_k','R25',None),('D3_a','T25',None),('C22n_f','S19','U19'),('C22n_g','S22','U22'),('C1n_c','I10','K10'),
('R10k_d','J13','O13'),('C100p_b','I16','J16'),('C1u_c-','M16','O16'),('C100u_b-','M10','N10'),('C100p_c','O10','P10'),
('R10k_e','O9','S9'),('R68k','Q10','T10'),('C10u+','S11','U11'),('C100u_a-','L2','M2'),('R470k_a','I5','I8'),
('C2n2','J5','J7'),('C100n_c','L7','M7'),('R22k_b','K8','P8'),('R8M2','N7','Q7'),('C100n_d','S3','U3'),
('R3M3','R4','U4'),('C1u_d-','R6','T6'),('R1M_c','Q8','U8')]
pins={}
for name,col0,rows in [('IC1',3,'NOPQ'),('IC2',7,'EFGH'),('IC3',17,'IJKL'),('IC4',13,'RSTU')]:
    col1=col0+3
    for i,r in enumerate(rows): pins[f'{name}.{i+1}']=(r,col0); pins[f'{name}.{8-i}']=(r,col1)
ext={'Gain1':'A1','Gain2':'G1','Gain3':'I1','Input':'R1','Ground':'U1','Mid2':'A26','Vol3':'B26','Treble1':'C26',
'Treble2':'D26','Treble3':'E26','Bass2':'F26','Deep2':'G26','Deep1':'L26','Vol1':'M26','Mid1':'N26','Pres3':'O26',
'LED+':'P26','9V':'T26','Pres12':'U26'}
nets={}
def add(key,label):
    nets.setdefault(f(key),[]).append(label)
for n,a,b in comps:
    add(h(a),n+'.1')
    if b: add(h(b),n+'.2')
for p,k in pins.items(): add(k,p)
for e,k in ext.items(): add(h(k),'**'+e)
for k,v in sorted(nets.items(), key=lambda kv: str(kv[0])):
    print(sorted(v))
