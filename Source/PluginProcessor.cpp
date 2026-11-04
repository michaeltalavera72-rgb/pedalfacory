#include "PluginProcessor.h"
#include "PluginEditor.h"

juce::AudioProcessorValueTreeState::ParameterLayout
PedalboardProcessor::makeLayout(std::vector<std::unique_ptr<PedalBase>>& pedals)
{
    // Register pedals here. Add new pedals to this list.
    pedals.push_back(std::make_unique<RamhornFuzz>());
    pedals.push_back(std::make_unique<Buzzsaw>());
    pedals.push_back(std::make_unique<RailBender>());
    pedals.push_back(std::make_unique<ValveHowler>());
    pedals.push_back(std::make_unique<FeralHound>());
    pedals.push_back(std::make_unique<SlowBurn>());
    pedals.push_back(std::make_unique<Gatekeeper>());
    pedals.push_back(std::make_unique<Overdrive>());
    pedals.push_back(std::make_unique<Distortion>());
    pedals.push_back(std::make_unique<Fuzz>());
    juce::AudioProcessorValueTreeState::ParameterLayout layout;
    // Board input/output level. Input sets how hard the first pedal is driven.
    auto db = [](float v, int) { return juce::String(v, 1) + " dB"; };
    layout.add(std::make_unique<juce::AudioParameterFloat>(juce::ParameterID{"board_in",1}, "Input Level",
        juce::NormalisableRange<float>(-24.0f, 24.0f, 0.1f), 0.0f,
        juce::AudioParameterFloatAttributes().withLabel("dB").withStringFromValueFunction(db)));
    layout.add(std::make_unique<juce::AudioParameterFloat>(juce::ParameterID{"board_out",1}, "Output Level",
        juce::NormalisableRange<float>(-60.0f, 12.0f, 0.1f, 2.5f), 0.0f,          // skewed: fine control near 0 dB
        juce::AudioParameterFloatAttributes().withLabel("dB").withStringFromValueFunction(db)));
    for (auto& p : pedals) p->addParameters(layout);
    return layout;
}

PedalboardProcessor::PedalboardProcessor()
    : AudioProcessor(BusesProperties()
          .withInput("Input", juce::AudioChannelSet::stereo(), true)
          .withOutput("Output", juce::AudioChannelSet::stereo(), true)),
      apvts(*this, nullptr, "STATE", makeLayout(pedals))
{
    for (auto& p : pedals) p->bindParameters(apvts);
    inGainDb = apvts.getRawParameterValue("board_in");
    outGainDb = apvts.getRawParameterValue("board_out");
    setBoard(juce::StringArray(board));   // copy: setBoard clears board while reading ids
}

PedalBase* PedalboardProcessor::findPedal(const juce::String& id) const
{
    for (auto& p : pedals) if (p->getId() == id) return p.get();
    return nullptr;
}
juce::StringArray PedalboardProcessor::getBoard() const
{
    const juce::SpinLock::ScopedLockType l(boardLock);
    return board;
}
void PedalboardProcessor::setBoard(const juce::StringArray& ids)
{
    {
        const juce::SpinLock::ScopedLockType l(boardLock);
        board.clear(); chainSize = 0;
        for (auto& id : ids)
            if (auto* p = findPedal(id); p != nullptr && ! board.contains(id) && chainSize < maxSlots)
            { board.add(id); chain[chainSize++] = p; }
        apvts.state.setProperty("board", board.joinIntoString(","), nullptr);
    }
    sendChangeMessage();
}

void PedalboardProcessor::prepareToPlay(double sr, int bs)
{
    // Pedals are mono, like the real thing: one channel in, one channel through the chain.
    juce::dsp::ProcessSpec spec{ sr, (juce::uint32) bs, 1 };
    for (auto& p : pedals) { p->prepare(spec); p->reset(); }
    inGain.reset(sr, 0.05);  inGain.setCurrentAndTargetValue(juce::Decibels::decibelsToGain(inGainDb->load()));
    outGain.reset(sr, 0.05); outGain.setCurrentAndTargetValue(juce::Decibels::decibelsToGain(outGainDb->load()));
}

void PedalboardProcessor::processBlock(juce::AudioBuffer<float>& buf, juce::MidiBuffer&)
{
    juce::ScopedNoDenormals nd;
    const int numSamples = buf.getNumSamples();
    if (buf.getNumChannels() == 0 || numSamples == 0) return;
    if (getTotalNumInputChannels() == 0) buf.clear();

    // Guitar comes in on input 1. Run the chain on that channel only (no allocation:
    // this buffer just points at channel 0), then copy the result to every output.
    juce::AudioBuffer<float> mono(buf.getArrayOfWritePointers(), 1, numSamples);

    // INPUT level (smoothed) + input meter
    inGain.setTargetValue(juce::Decibels::decibelsToGain(inGainDb->load()));
    inGain.applyGain(mono, numSamples);
    raisePeak(inPeak, mono.getMagnitude(0, 0, numSamples));

    PedalBase* local[maxSlots]; int n = 0;
    {
        const juce::SpinLock::ScopedTryLockType l(boardLock);
        if (l.isLocked()) { n = chainSize; for (int i = 0; i < n; ++i) local[i] = chain[i]; }
        // if the board is being edited right now, this block passes through dry
    }
    // Pedals with a return stage (keyed gate) listen at their slot and apply their gain later:
    // before the first time-based pedal, or after the last pedal.
    PedalBase* pending[maxSlots]; int np = 0;
    auto flushReturns = [&] { for (int k = 0; k < np; ++k) pending[k]->processReturn(mono); np = 0; };
    for (int i = 0; i < n; ++i)
        if (local[i]->isActive())
        {
            if (local[i]->isTimeBased()) flushReturns();
            local[i]->process(mono);
            if (local[i]->hasReturnStage()) pending[np++] = local[i];
        }
    flushReturns();

    // OUTPUT level (smoothed) + output meter
    outGain.setTargetValue(juce::Decibels::decibelsToGain(outGainDb->load()));
    outGain.applyGain(mono, numSamples);
    raisePeak(outPeak, mono.getMagnitude(0, 0, numSamples));

    for (int c = 1; c < buf.getNumChannels(); ++c)
        buf.copyFrom(c, 0, buf, 0, 0, numSamples);       // same signal on left and right
}

juce::AudioProcessorEditor* PedalboardProcessor::createEditor() { return new PedalboardEditor(*this); }

void PedalboardProcessor::getStateInformation(juce::MemoryBlock& d)
{
    if (auto xml = apvts.copyState().createXml()) copyXmlToBinary(*xml, d);
}
void PedalboardProcessor::setStateInformation(const void* d, int n)
{
    if (auto xml = getXmlFromBinary(d, n))
    {
        apvts.replaceState(juce::ValueTree::fromXml(*xml));
        juce::StringArray ids; ids.addTokens(apvts.state.getProperty("board", "bm").toString(), ",", "");
        setBoard(ids);
    }
}
juce::AudioProcessor* JUCE_CALLTYPE createPluginFilter() { return new PedalboardProcessor(); }
