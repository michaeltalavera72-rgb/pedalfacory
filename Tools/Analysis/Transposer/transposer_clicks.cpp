#define main main_unused
#include "transposer_quality.cpp"
#undef main
struct Biq{ double b0,b1,b2,a1,a2,x1=0,x2=0,y1=0,y2=0; float p(float x){ double y=b0*x+b1*x1+b2*x2-a1*y1-a2*y2; x2=x1;x1=x;y2=y1;y1=y; return (float)y;} };
struct HP4 { Biq a,b; HP4(double f){ auto mk=[&](double q){ double w0=2*PI*f/SR,c=std::cos(w0),al=std::sin(w0)/(2*q),a0=1+al; Biq h; h.b0=(1+c)/2/a0; h.b1=-(1+c)/a0; h.b2=h.b0; h.a1=-2*c/a0; h.a2=(1-al)/a0; return h; }; a=mk(0.5412); b=mk(1.3065);} float p(float x){ return b.p(a.p(x)); } };

int main(){
  struct Ev{ const char* name; std::function<void(Transposer&)> before, at; };
  std::vector<Ev> evs={
   {"0 -> -1 st", [](Transposer& t){t.setSemitones(0);}, [](Transposer& t){t.setSemitones(-1);}},
   {"-1 -> -2 st",[](Transposer& t){t.setSemitones(-1);},[](Transposer& t){t.setSemitones(-2);}},
   {"-2 -> 0 st", [](Transposer& t){t.setSemitones(-2);},[](Transposer& t){t.setSemitones(0);}},
   {"-2 -> +5 st",[](Transposer& t){t.setSemitones(-2);},[](Transposer& t){t.setSemitones(5);}},
   {"-12 -> +12", [](Transposer& t){t.setSemitones(-12);},[](Transposer& t){t.setSemitones(12);}},
   {"ON -> OFF (-2)",[](Transposer& t){t.setSemitones(-2);},[](Transposer& t){t.setOn(false);}},
   {"OFF -> ON (-2)",[](Transposer& t){t.setSemitones(-2); t.setOn(false);},[](Transposer& t){t.setOn(true);}},
   {"LIVE -> STUDIO (-2)",[](Transposer& t){t.setSemitones(-2);},[](Transposer& t){t.setMode(Transposer::Mode::studio);}},
   {"STUDIO -> LIVE (-2)",[](Transposer& t){t.setSemitones(-2); t.setMode(Transposer::Mode::studio);},[](Transposer& t){t.setMode(Transposer::Mode::live);}},
   {"MIX 100 -> 0 (-2)",[](Transposer& t){t.setSemitones(-2);},[](Transposer& t){t.setMix(0);}},
   {"LEVEL 0 -> +12 dB",[](Transposer& t){t.setSemitones(-2);},[](Transposer& t){t.setLevelDb(12);}},
   {"steady -2 (baseline)",[](Transposer& t){t.setSemitones(-2);},[](Transposer& t){}},
   {"steady 0 (baseline)",[](Transposer& t){t.setSemitones(0);},[](Transposer& t){}},
  };
  for(double f0: {82.4069, 196.0}) { printf("-- input %.1f Hz tone --\n",f0);
  for(auto& e: evs){
    auto x=tone(f0,2.0,4); Transposer t; t.setOn(true); t.setMode(Transposer::Mode::live); t.setMix(1); t.setLevelDb(0); e.before(t); t.prepare(SR,128);
    HP4 hp(4000); double pkBefore=0, pkAfter=0;
    for(size_t i=0;i<x.size();i+=128){ if(i==(size_t)SR) e.at(t); t.process(x.data()+i,128);
      for(int k=0;k<128;++k){ double h=std::abs(hp.p(x[i+k])); if(i>=(size_t)(0.5*SR)&&i<(size_t)SR) pkBefore=std::max(pkBefore,h); if(i>=(size_t)SR&&i<(size_t)(1.5*SR)) pkAfter=std::max(pkAfter,h);} }
    printf("%-22s HF(>4k) peak before %6.1f dBFS, around event %6.1f dBFS\n",e.name,20*std::log10(pkBefore+1e-9),20*std::log10(pkAfter+1e-9)); } }
  // hard-switch reference: what an un-smoothed jump from tone to silence looks like
  { auto x=tone(82.4069,2.0,4); HP4 hp(4000); double pk=0; for(size_t i=0;i<x.size();++i){ float v= i<SR? x[i]:0.f; pk=std::max(pk,(double)std::abs(hp.p(v))); } printf("reference: hard cut to silence = %.1f dBFS HF peak (a click)\n",20*std::log10(pk)); }
}
