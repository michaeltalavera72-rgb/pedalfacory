#include "PluginEditor.h"

// ---------------- PedalStrip ----------------
PedalStrip::PedalStrip(PedalboardProcessor& p, PedalBase& pd, BoardComponent& b)
    : pedal(pd), board(b), face(createFaceFor(pd.getId()))
{
    addAndMakeVisible(remove);
    remove.onClick = [this] { board.removePedal(pedal); };
    auto& bypassButton = face ? static_cast<juce::Button&>(footswitch) : static_cast<juce::Button&>(bypass);
    addAndMakeVisible(bypassButton);
    bypassAtt = std::make_unique<juce::AudioProcessorValueTreeState::ButtonAttachment>(
        p.apvts, pd.getId() + "_bypass", bypassButton);
    for (auto& id : pd.knobIds)
    {
        const bool detent = pd.detentKnobIds.contains(id);
        auto* s = knobs.add(detent ? new DetentSlider() : new juce::Slider(juce::Slider::RotaryVerticalDrag, juce::Slider::NoTextBox));
        if (detent) s->setDoubleClickReturnValue(true, 0.5);     // range is 0..1 (attachment), noon = 0.5
        auto* l = labels.add(new juce::Label({}, p.apvts.getParameter(id)->getName(40)));
        l->setJustificationType(juce::Justification::centred);
        l->setInterceptsMouseClicks(false, false);
        if (face)
        {
            auto* look = face->knobLookAndFeel();
            s->setLookAndFeel(look != nullptr ? look : &knobLook);
            s->setRotaryParameters(juce::MathConstants<float>::pi * 1.25f,
                                   juce::MathConstants<float>::pi * 2.75f, true);   // -135..+135 deg (= Blender filmstrip)
            l->setText(l->getText().toUpperCase(), juce::dontSendNotification);
            l->setFont(juce::FontOptions(11.5f, juce::Font::bold));
            l->setColour(juce::Label::textColourId, face->labelColour());
        }
        addAndMakeVisible(s); addChildComponent(l); l->setVisible(! (face && face->drawsLabels()));
        atts.push_back(std::make_unique<juce::AudioProcessorValueTreeState::SliderAttachment>(p.apvts, id, *s));
    }
    if (face)
    {
        footswitch.imageFor = [this](bool down) { return face->footswitchImage(down); };
        if (pd.secondarySwitchId().isNotEmpty())
        {
            footswitch2.imageFor = footswitch.imageFor;
            addAndMakeVisible(footswitch2);
            secondAtt = std::make_unique<juce::AudioProcessorValueTreeState::ButtonAttachment>(
                p.apvts, pd.secondarySwitchId(), footswitch2);
            footswitch.setTooltip("Drive on/off");
            footswitch2.setTooltip(pd.secondarySwitchLabel() + " on/off");
        }
        startTimerHz(20);
    }
    lastPrimary = pedal.primaryOn(); lastSecondary = pedal.secondaryOn();
}
PedalStrip::~PedalStrip()
{
    for (auto* s : knobs) s->setLookAndFeel(nullptr);
}
void PedalStrip::timerCallback()
{
    // repaint the LEDs when a switch changes (mouse or host automation)
    if (pedal.primaryOn() != lastPrimary || pedal.secondaryOn() != lastSecondary)
    {
        lastPrimary = pedal.primaryOn(); lastSecondary = pedal.secondaryOn();
        repaint();
    }
}
FaceLayout PedalStrip::layout() const
{
    auto f = FaceLayout::make(bodyBounds(), knobs.size(), numSwitches());
    f.secondaryOn = pedal.secondaryOn();
    return f;
}
juce::Rectangle<float> PedalStrip::bodyBounds() const
{
    return getLocalBounds().toFloat().withTrimmedTop((float) BoardComponent::headerH + 4.0f).reduced(2.0f, 2.0f);
}
void PedalStrip::paint(juce::Graphics& g)
{
    // header: drag handle + name
    auto head = getLocalBounds().removeFromTop(BoardComponent::headerH).toFloat().reduced(2.0f, 0.0f);
    g.setColour(dragging ? juce::Colour(0xff3b8ce0) : juce::Colour(0xff2e3236));
    g.fillRoundedRectangle(head, 6.0f);
    g.setColour(juce::Colours::white.withAlpha(0.8f));
    for (int i = 0; i < 3; ++i) g.fillEllipse(head.getX() + 10.0f + (float) i * 7.0f, head.getCentreY() - 2.0f, 4.0f, 4.0f);
    g.setFont(juce::FontOptions(14.0f, juce::Font::bold));
    g.drawText(pedal.getName(), head, juce::Justification::centred);

    auto body = bodyBounds();
    if (face)
    {
        face->paint(g, layout(), pedal.primaryOn());
        return;
    }
    g.setColour(juce::Colour(0xff2b6cb0));
    g.fillRoundedRectangle(body, 10.0f);
}
void PedalStrip::resized()
{
    auto head = getLocalBounds().removeFromTop(BoardComponent::headerH).reduced(4, 3);
    remove.setBounds(head.removeFromRight(22));
    if (face)
    {
        auto f = layout();
        for (int i = 0; i < knobs.size(); ++i)
        {
            knobs[i]->setBounds(face->knobBounds(f.knobs[i]).toNearestInt());
            labels[i]->setBounds(f.labels[i].toNearestInt());
        }
        footswitch.setBounds(face->switchBounds(f.footswitch).toNearestInt());
        if (f.twoSwitches) footswitch2.setBounds(face->switchBounds(f.footswitch2).toNearestInt());
        return;
    }
    auto r = bodyBounds().toNearestInt().reduced(8);
    bypass.setBounds(r.removeFromBottom(26));
    if (knobs.isEmpty()) return;
    r = r.withSizeKeepingCentre(r.getWidth(), juce::jmin(r.getHeight(), 110));
    int w = r.getWidth() / knobs.size();
    for (int i = 0; i < knobs.size(); ++i)
    {
        auto c = r.removeFromLeft(w);
        labels[i]->setBounds(c.removeFromBottom(20));
        knobs[i]->setBounds(c);
    }
}
juce::String PedalStrip::getTooltip()
{
    const auto basedOn = pedal.getBasedOn();
    if (basedOn.isEmpty() || dragging) return {};
    const auto pos = getMouseXYRelative().toFloat();
    bool overName = pos.y < (float) BoardComponent::headerH;
    if (face)
    {
        const auto f = layout();
        overName = overName || f.name.contains(pos) || f.subtitle.contains(pos);
    }
    if (! overName) return {};
    if (basedOn.startsWith("Generic")) return basedOn;
    return "Based on the " + basedOn + "\n"
           "Product names belong to their owners and are used only to identify the circuit modelled; "
           "not affiliated with or endorsed by them.";
}
void PedalStrip::mouseDown(const juce::MouseEvent& e)
{
    headerDrag = e.getPosition().y < BoardComponent::headerH;
    if (headerDrag) { dragging = true; setMouseCursor(juce::MouseCursor::DraggingHandCursor); board.beginDrag(*this); repaint(); }
}
void PedalStrip::mouseDrag(const juce::MouseEvent&) { if (headerDrag) board.dragTo(*this); }
void PedalStrip::mouseUp(const juce::MouseEvent&)
{
    if (! headerDrag) return;
    headerDrag = false; dragging = false;
    setMouseCursor(juce::MouseCursor::NormalCursor);
    board.endDrag(*this); repaint();
}

// ---------------- BoardComponent ----------------
BoardComponent::BoardComponent(PedalboardProcessor& p) : proc(p) { rebuild(); }

void BoardComponent::rebuild()
{
    auto ids = proc.getBoard();
    juce::StringArray current;
    for (auto* s : strips) current.add(s->pedal.getId());
    if (ids == current) return;                       // nothing changed (e.g. our own drop)
    animator.cancelAllAnimations(false);
    strips.clear();
    for (auto& id : ids)
        if (auto* pd = proc.findPedal(id)) addAndMakeVisible(strips.add(new PedalStrip(proc, *pd, *this)));
    setSize(juce::jmax(slotW, gap + strips.size() * (slotW + gap)), boardH);
    layoutSlots(false);
}
void BoardComponent::layoutSlots(bool animate)
{
    for (int i = 0; i < strips.size(); ++i)
    {
        if (strips[i]->dragging) continue;
        juce::Rectangle<int> b(slotX(i), 4, slotW, getHeight() - 8);
        if (animate) animator.animateComponent(strips[i], b, 1.0f, 150, false, 1.0, 1.0);
        else strips[i]->setBounds(b);
    }
}
void BoardComponent::beginDrag(PedalStrip& s)
{
    animator.cancelAllAnimations(true);
    dragged = &s;
    dragIndex = strips.indexOf(&s);
    grabOffset = getLocalPoint(nullptr, juce::Desktop::getMousePosition()).x - s.getX();
    s.toFront(false);
    startTimerHz(60);               // drives auto-scroll near the edges
}
void BoardComponent::dragTo(PedalStrip& s)
{
    int mx = getLocalPoint(nullptr, juce::Desktop::getMousePosition()).x;
    int x = juce::jlimit(0, juce::jmax(0, getWidth() - slotW), mx - grabOffset);
    s.setTopLeftPosition(x, s.getY());
    int target = juce::jlimit(0, strips.size() - 1, (x + slotW / 2) / (slotW + gap));
    if (target != dragIndex)
    {
        strips.move(dragIndex, target);
        dragIndex = target;
        layoutSlots(true);          // the other pedals slide out of the way
    }
}
void BoardComponent::timerCallback()
{
    if (dragged == nullptr || viewport == nullptr) { stopTimer(); return; }
    // Mouse position relative to the visible area (not the full-width board)
    auto p = viewport->getLocalPoint(nullptr, juce::Desktop::getMousePosition());
    const int edge = 60, maxSpeed = 24, w = viewport->getMaximumVisibleWidth();
    int speed = 0;
    if (p.x < edge)          speed = -juce::jmap(juce::jmax(0, p.x), 0, edge, maxSpeed, 2);
    else if (p.x > w - edge) speed =  juce::jmap(juce::jmin(w, p.x), w - edge, w, 2, maxSpeed);
    if (speed != 0)
    {
        auto pos = viewport->getViewPosition();
        viewport->setViewPosition(juce::jlimit(0, juce::jmax(0, getWidth() - w), pos.x + speed), pos.y);
        dragTo(*dragged);           // keep the pedal under the cursor as the view moves
    }
}
void BoardComponent::endDrag(PedalStrip& s)
{
    stopTimer();
    dragged = nullptr;
    animator.animateComponent(&s, { slotX(dragIndex), 4, slotW, getHeight() - 8 }, 1.0f, 120, false, 1.0, 1.0);
    juce::StringArray ids;
    for (auto* p : strips) ids.add(p->pedal.getId());
    proc.setBoard(ids);             // commit new order to the audio chain + saved state
    dragIndex = -1;
}
void BoardComponent::removePedal(PedalBase& p)
{
    auto ids = proc.getBoard(); ids.removeString(p.getId());
    juce::MessageManager::callAsync([this, ids] { proc.setBoard(ids); });   // don't delete the button mid-click
}

// ---------------- Editor ----------------
PedalboardEditor::PedalboardEditor(PedalboardProcessor& p)
    : AudioProcessorEditor(p), proc(p), board(p),
      inputLevel("INPUT", p.apvts, "board_in", [&p] { return PedalboardProcessor::takePeak(p.inPeak); }),
      outputLevel("OUTPUT", p.apvts, "board_out", [&p] { return PedalboardProcessor::takePeak(p.outPeak); })
{
    addAndMakeVisible(inputLevel); addAndMakeVisible(outputLevel);
    viewport.setViewedComponent(&board, false);
    board.setViewport(&viewport);
    viewport.setScrollBarsShown(false, true);
    addAndMakeVisible(viewport); addAndMakeVisible(addButton);
    addButton.onClick = [this]
    {
        juce::PopupMenu m; auto onBoard = proc.getBoard(); int i = 1;
        for (auto& pd : proc.pedals) m.addItem(i++, pd->getName(), ! onBoard.contains(pd->getId()));
        m.showMenuAsync(juce::PopupMenu::Options().withTargetComponent(addButton), [this](int r)
        {
            if (r <= 0) return;
            auto ids = proc.getBoard(); ids.add(proc.pedals[(size_t) r - 1]->getId()); proc.setBoard(ids);
        });
    };
    proc.addChangeListener(this);
    setResizable(true, true); setResizeLimits(minWidth, BoardComponent::boardH + topBarH + 14, 2400, BoardComponent::boardH + topBarH + 14);
    updateSize();
}
PedalboardEditor::~PedalboardEditor() { proc.removeChangeListener(this); }
void PedalboardEditor::updateSize() { setSize(juce::jlimit(minWidth, 1400, board.getWidth() + 8), BoardComponent::boardH + topBarH + 14); }
void PedalboardEditor::paint(juce::Graphics& g)
{
    g.fillAll(juce::Colour(0xff1a1a1a));
    g.setColour(juce::Colour(0xff232629));
    g.fillRect(getLocalBounds().removeFromTop(topBarH));
}
void PedalboardEditor::resized()
{
    auto r = getLocalBounds();
    auto bar = r.removeFromTop(topBarH).reduced(8, 6);
    inputLevel.setBounds(bar.removeFromLeft(240));
    outputLevel.setBounds(bar.removeFromRight(240));
    addButton.setBounds(bar.withSizeKeepingCentre(130, 28));
    viewport.setBounds(r);
}
