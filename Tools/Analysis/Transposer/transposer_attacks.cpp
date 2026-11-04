#define main main_unused
#include "transposer_quality.cpp"
#undef main
// Picked-playing test: 40 plucks (single notes and chords) that ring into each other.
std::vector<size_t> onsetsOf(const std::vector<float>& y){ std::vector<size_t> on; double fast=0,slow=0; size_t last=0; bool any=false;
  double af=std::exp(-1/(0.0005*SR)), rf=std::exp(-1/(0.005*SR)), as=std::exp(-1/(0.030*SR));
  for(size_t i=0;i<y.size();++i){ double a=std::abs(y[i]); fast = a>fast? af*fast+(1-af)*a : rf*fast+(1-rf)*a; slow=as*slow+(1-as)*fast;
    if(fast>0.004 && fast>2.2*slow && (!any || i-last>(size_t)(0.035*SR))){ on.push_back(i); last=i; any=true; } }
  return on; }
int main(int argc,char**argv){ std::mt19937 rng(7); std::uniform_real_distribution<double> u(0,1);
  const double notes[]={82.41,98.0,110.0,123.47,146.83,164.81,196.0,220.0,246.94,329.63};
  size_t N=(size_t)(12*SR); std::vector<float> x(N,0.f); std::vector<size_t> truth; size_t t=(size_t)(0.3*SR);
  for(int e=0;e<40;++e){ std::vector<double> fs; if(u(rng)<0.4){ fs={82.41,123.47,164.81}; if(u(rng)<0.5) fs={110.0,164.81,220.0,261.63}; } else fs={notes[(int)(u(rng)*10)]};
    auto p=pluck(fs,1.2,0.5,(unsigned)e+1); for(size_t i=0;i<p.size()&&t+i<N;++i) x[t+i]+=p[i]; truth.push_back(t); t+=(size_t)((0.12+0.25*u(rng))*SR); }
  auto inOn=onsetsOf(x);
  printf("input: %zu plucks, detector finds %zu onsets\n",truth.size(),inOn.size());
  for(int st: {0,-1,-2,-5,-12,1,2,5,12}) for(auto m: {Transposer::Mode::live}) {
    auto r=run(x,st,m,1); auto o=onsetsOf(r.y);
    int hit=0, miss=0; double lat=0, latMax=0; std::vector<char> used(o.size(),0);
    for(size_t ti: inOn){ int found=-1; for(size_t k=0;k<o.size();++k) if(!used[k] && o[k]+ (size_t)(0.002*SR)>=ti && o[k]<=ti+(size_t)(0.045*SR)){ found=(int)k; break; }
      if(found>=0){ used[found]=1; ++hit; double l=((double)o[found]-(double)ti)/SR*1000; lat+=l; latMax=std::max(latMax,l);} else { ++miss; if(st==-1) printf("   miss at %.3f s\n",ti/SR);} }
    int extra=0; for(char c: used) if(!c) ++extra;
    printf("%+3d st: attacks found %d/%zu (missing %d), extra attacks %d, attack delay avg %.1f ms max %.1f ms, avg head delay %.1f ms\n",st,hit,inOn.size(),miss,extra,lat/std::max(1,hit),latMax,r.avgDelay); } }
