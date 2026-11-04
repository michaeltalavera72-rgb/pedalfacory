#define main main_unused
#include "transposer_quality.cpp"
#undef main
int main(){
 for(double sr: {44100.0, 48000.0, 96000.0}) for(auto m: {Transposer::Mode::live, Transposer::Mode::studio}) for(int st: {-2, 0, 3}) {
   // tone burst starting at 0.5 s after silence; onset detection on output
   size_t N=(size_t)(1.5*sr); std::vector<float> x(N,0.f); size_t on=(size_t)(0.5*sr);
   for(size_t i=on;i<N;++i){ double s=0; for(int k=1;k<=4;++k) s+=std::sin(2*PI*196.0*k*(i-on)/sr)/k; x[i]=(float)(0.3*s); }
   Transposer t; t.setSemitones(st); t.setOn(true); t.setMode(m); t.setMix(1); t.setLevelDb(0); t.prepare(sr,256);
   auto t0=std::chrono::steady_clock::now();
   for(size_t i=0;i<N;i+=256) t.process(x.data()+i,(int)std::min<size_t>(256,N-i));
   double us=std::chrono::duration<double,std::micro>(std::chrono::steady_clock::now()-t0).count()/(N/sr);
   size_t o=0; for(size_t i=0;i<N;++i) if(std::abs(x[i])>0.02){o=i;break;}
   printf("%6.0f Hz %-6s %+d st: onset delay %6.2f ms  reported %5d samples (%5.1f ms)  CPU %.2f%% of one core\n",sr,m==Transposer::Mode::live?"LIVE":"STUDIO",st,(double)((long)o-(long)on)/sr*1000,t.reportedLatency(),t.reportedLatency()/sr*1000,us/1e4);
 } }
