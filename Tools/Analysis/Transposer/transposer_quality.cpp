#include "Global/Transposer.h"
#include <cstdio>
#include <complex>
#include <chrono>
#include <random>
using namespace transposer;
const double SR = 48000.0;
const double PI = 3.14159265358979;

std::vector<float> tone(double f, double secs, int harm=10, double amp=0.3) {
  std::vector<float> v((size_t)(secs*SR));
  for (size_t i=0;i<v.size();++i){ double s=0; for(int k=1;k<=harm;++k) s+=std::sin(2*PI*f*k*i/SR + k*0.7)/k; v[i]=(float)(amp*s*0.5);} return v; }
std::vector<float> pluck(std::vector<double> fs, double secs, double amp=0.3, unsigned seed=1) {
  std::vector<float> v((size_t)(secs*SR),0.f); std::mt19937 rng(seed); std::uniform_real_distribution<float> u(-1,1);
  for (size_t ni=0; ni<fs.size(); ++ni){ double f=fs[ni]; int N=(int)std::lround(SR/f); std::vector<float> d(N); for(auto&x:d)x=u(rng); int p=0; float prev=0;
    int start = (int)(0.012*SR*ni); // strum
    for(size_t i=start;i<v.size();++i){ float y=d[p]; int q=(p+1)%N; float nv=0.4985f*(d[p]+d[q]); d[p]=nv; p=q; v[i]+=y*amp/fs.size()*2; } }
  return v; }


void fft(std::vector<std::complex<double>>& a){ size_t n=a.size(); for(size_t i=1,j=0;i<n;++i){ size_t bit=n>>1; for(;j&bit;bit>>=1) j^=bit; j^=bit; if(i<j) std::swap(a[i],a[j]); }
  for(size_t len=2;len<=n;len<<=1){ double ang=-2*PI/len; std::complex<double> wl(std::cos(ang),std::sin(ang)); for(size_t i=0;i<n;i+=len){ std::complex<double> w=1; for(size_t j=0;j<len/2;++j){ auto u=a[i+j], v=a[i+j+len/2]*w; a[i+j]=u+v; a[i+j+len/2]=u-v; w*=wl; } } } }
// spectrum analysis of a steady harmonic tone: measured fundamental + energy NOT in the harmonics (dB re total)
void analyse(const std::vector<float>& y, size_t a, double fExp, double& fGot, double& residueDb) {
  const size_t N=1<<17; std::vector<std::complex<double>> X(N); for(size_t i=0;i<N;++i){ double w=0.5-0.5*std::cos(2*PI*i/(N-1)); X[i]=w*y[a+i]; }
  fft(X); std::vector<double> m(N/2); for(size_t i=0;i<N/2;++i) m[i]=std::norm(X[i]);
  double binHz=SR/N; size_t c=(size_t)std::lround(fExp/binHz), lo=(size_t)(c*0.94), hi=(size_t)(c*1.06), pk=lo;
  for(size_t i=lo;i<=hi;++i) if(m[i]>m[pk]) pk=i;
  double l=std::sqrt(m[pk-1]),cc=std::sqrt(m[pk]),r=std::sqrt(m[pk+1]); double d=0.5*(l-r)/(l-2*cc+r); fGot=(pk+d)*binHz;
  double tot=0,harm=0; for(size_t i=2;i<N/2;++i){ tot+=m[i]; }
  for(int k=1;k*fExp<SR/2;++k){ size_t hc=(size_t)std::lround(k*fGot/binHz); for(size_t i=hc-4;i<=hc+4;++i) harm+=m[i]; }
  residueDb=10*std::log10(std::max(1e-20,(tot-harm)/tot)); }
// envelope flutter: RMS over whole periods of the output, max/min in dB
double flutter(const std::vector<float>& y, size_t a, size_t b, double fOut){ int W=(int)std::lround(std::ceil(0.010*fOut)*SR/fOut); double mn=1e9,mx=0;
  for(size_t i=a;i+W<b;i+=W/4){ double e=0; for(int k=0;k<W;++k) e+=y[i+k]*y[i+k]; e=std::sqrt(e/W); mn=std::min(mn,e); mx=std::max(mx,e);} return 20*std::log10(mx/mn); }
struct Run { std::vector<float> y; double avgDelay=0; long splices=0; double usPerSec=0; };
Run run(std::vector<float> x, int st, Transposer::Mode m, float mix=1, SpliceShifter::Tuning tn={}, std::function<void(Transposer&,size_t)> ev=nullptr) {
  Transposer t; t.live.tune=tn; t.setSemitones(st); t.setOn(true); t.setMode(m); t.setMix(mix); t.setLevelDb(0);
  t.prepare(SR, 256); Run r; double dsum=0; long dn=0;
  auto t0=std::chrono::steady_clock::now();
  for(size_t i=0;i<x.size();i+=256){ if(ev) ev(t,i); int n=(int)std::min<size_t>(256,x.size()-i); t.process(x.data()+i,n); dsum+=t.liveDelaySamples(); dn++; }
  auto t1=std::chrono::steady_clock::now();
  r.usPerSec = std::chrono::duration<double,std::micro>(t1-t0).count()/(x.size()/SR);
  r.y=x; r.avgDelay=dsum/dn/SR*1000; r.splices=t.liveSplices(); return r; }

double chordResidue(const std::vector<float>& y, size_t a, std::vector<double> fs, double tolHz=1.5){
  const size_t N=1<<17; std::vector<std::complex<double>> X(N); for(size_t i=0;i<N;++i){ double w=0.5-0.5*std::cos(2*PI*i/(N-1)); X[i]=w*y[a+i]; }
  fft(X); std::vector<double> m(N/2); for(size_t i=0;i<N/2;++i) m[i]=std::norm(X[i]); double binHz=SR/N;
  std::vector<char> mark(N/2,0); for(double f: fs) for(int k=1;k*f<SR/2-10;++k){ size_t hc=(size_t)std::lround(k*f/binHz); int tb=(int)std::ceil(tolHz/binHz); for(size_t i=hc-tb;i<=hc+tb;++i) mark[i]=1; }
  double tot=0,res=0; for(size_t i=2;i<N/2;++i){ tot+=m[i]; if(!mark[i]) res+=m[i]; } return 10*std::log10(res/tot); }
std::vector<float> chord(std::vector<double> fs,double secs){ std::vector<float> v((size_t)(secs*SR),0.f); int n=0; for(double f: fs){ auto t=tone(f,secs,8,0.6/fs.size()); for(size_t i=0;i<v.size();++i) v[i]+=t[i]*(1+0.0*n); ++n;} return v; }
int main(int argc,char**argv){
  SpliceShifter::Tuning tn;
  if(argc>1){ tn.maxDelayMs=atof(argv[1]); } if(argc>2) tn.crossfadeMs=atof(argv[2]); if(argc>3) tn.matchWindowMs=atof(argv[3]); if(argc>4) tn.goodMatch=atof(argv[4]); if(argc>5) tn.minJumpMs=atof(argv[5]);
  const double E2=82.4069;
  printf("== Pitch accuracy (sustained low E, harmonics 1-10) ==\n");
  for(auto m: {Transposer::Mode::live, Transposer::Mode::studio}){
    for(int st: {-12,-5,-2,-1,0,1,2,5,12}){
      auto r=run(tone(E2,3.0),st,m,1,tn); double fe=E2*std::pow(2,st/12.0);
      double f,res; analyse(r.y,(size_t)(0.25*SR),fe,f,res); double fl=flutter(r.y,(size_t)(0.5*SR),(size_t)(2.9*SR),fe);
      printf("%s %+3d st: expect %7.3f got %7.3f Hz (%+6.2f c) | residue %6.1f dB  flutter %5.2f dB  splices/s %5.1f  avg delay %5.2f ms  CPU %.0f us/s\n",
        m==Transposer::Mode::live?"LIVE  ":"STUDIO",st,fe,f,1200*std::log2(f/fe),res,fl,r.splices/3.0,r.avgDelay,r.usPerSec);
    }}
  // reference: unprocessed tone quality
  { auto x=tone(E2,3.0); double f,res; analyse(x,(size_t)(0.25*SR),E2,f,res); printf("reference dry: %.3f Hz residue %.1f dB flutter %.2f dB\n",f,res,flutter(x,(size_t)(0.5*SR),(size_t)(2.9*SR),E2)); }
  printf("== Sustained chords: residue (energy outside the shifted notes' harmonics) ==\n");
  std::vector<std::pair<const char*,std::vector<double>>> chords={{"E5 power",{82.41,123.47,164.81}},{"open E maj",{82.41,123.47,164.81,207.65,246.94,329.63}},{"open G maj",{98.0,123.47,146.83,196.0,246.94,392.0}}};
  for(auto& ch: chords){ auto x=chord(ch.second,3.0); printf("%s dry residue %.1f dB; live 0st %.1f\n",ch.first,chordResidue(x,(size_t)(0.25*SR),ch.second),chordResidue(run(x,0,Transposer::Mode::live).y,(size_t)(0.25*SR),ch.second)); }
  for(auto& ch: chords) for(int st: {-1,-2,-5,-12,1,12}) {
    std::vector<double> sh; for(double f: ch.second) sh.push_back(f*std::pow(2,st/12.0));
    auto rl=run(chord(ch.second,3.0),st,Transposer::Mode::live,1,tn); double dl=rl.avgDelay; auto rs=run(chord(ch.second,3.0),st,Transposer::Mode::studio,1,tn);
    printf("%-11s %+3d st: LIVE %6.1f / %6.1f dB   STUDIO %6.1f / %6.1f dB  (strict / >8 Hz)  live splices/s %.1f avg delay %.1f ms\n",ch.first,st,chordResidue(rl.y,(size_t)(0.25*SR),sh),chordResidue(rl.y,(size_t)(0.25*SR),sh,8),chordResidue(rs.y,(size_t)(0.25*SR),sh),chordResidue(rs.y,(size_t)(0.25*SR),sh,8),rl.splices/3.0,dl); }
  printf("== Chords (plucked open E major, live) ==\n");
  for(int st: {-1,-2,-5,-12,12}){ auto x=pluck({82.41,123.47,164.81,207.65,246.94,329.63},3.0); auto r=run(x,st,Transposer::Mode::live,1,tn);
    printf("LIVE %+3d st: splices/s %.1f avg delay %.2f ms\n",st,r.splices/3.0,r.avgDelay); }
  return 0; }
