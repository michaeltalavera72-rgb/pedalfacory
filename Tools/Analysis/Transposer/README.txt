Semitone Transposer test programs (plain C++17, no JUCE). They test Source/Global/Transposer.h directly.

  transposer_quality.cpp  pitch accuracy (cents), spectral residue on sustained notes and chords, splice rate, delay
  transposer_attacks.cpp  40 picked notes/chords: are attacks heard once, whole, and how late
  transposer_clicks.cpp   HF energy around knob/switch changes (a click would show ~ -19 dBFS)
  transposer_latency.cpp  onset delay vs reported latency, CPU, at 44.1/48/96 kHz

Build (Linux/macOS, or MSVC equivalent), with signalsmith-stretch and signalsmith-linear checked out:
  g++ -std=c++17 -O2 -I../../../Source -I<signalsmith-stretch>/include -I<signalsmith-linear>/include transposer_quality.cpp -o quality

Results 2026-11-04 (48 kHz): LIVE pitch within 0.5 cents at -5..+5 st; attacks 3 ms; sustained single
notes ~7 ms, chords ~13 ms; no clicks on any change (all < -50 dBFS HF); CPU ~1.2 % of one core.
STUDIO: ~85 ms reported latency, pitch on low E within ~5-10 cents.
