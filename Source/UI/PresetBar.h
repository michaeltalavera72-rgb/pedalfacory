#pragma once
#include <juce_gui_basics/juce_gui_basics.h>
#include "../Global/PresetManager.h"

// Preset row at the top of the editor:  PRESET  [<] [ name *        v ] [>]  [Save] [Save As...]
// Click the name for the menu (all presets, Default Board, Save / Save As / Rename / Delete, open the folder).
// "*" after the name = the board has changed since the preset was loaded or saved.
class PresetBar : public juce::Component, private juce::Timer
{
public:
    static constexpr int barH = 34;

    explicit PresetBar(PresetManager& m) : mgr(m)
    {
        for (auto* b : { &prev, &next, &save, &saveAs }) addAndMakeVisible(b);
        addAndMakeVisible(nameBox);
        prev.setTooltip("Previous preset");
        next.setTooltip("Next preset");
        save.setTooltip("Save the board over the current preset");
        saveAs.setTooltip("Save the board as a new preset");
        nameBox.setTooltip("Presets: pedals, their order and every setting, plus the transposer.\n"
                           "The INPUT and OUTPUT levels are not changed by presets.");
        prev.onClick = [this] { mgr.step(-1); refresh(); };
        next.onClick = [this] { mgr.step(+1); refresh(); };
        save.onClick = [this] { saveCurrent(); };
        saveAs.onClick = [this] { askName("Save Preset", "Name for this preset:", suggestedName(), [this](const juce::String& n) { saveAsName(n); }); };
        nameBox.onClick = [this] { showMenu(); };
        refresh();
        startTimerHz(4);
    }

    void paint(juce::Graphics& g) override
    {
        g.setColour(juce::Colours::white.withAlpha(0.55f));
        g.setFont(juce::FontOptions(12.0f, juce::Font::bold));
        g.drawText("PRESET", labelArea, juce::Justification::centredRight);
    }
    void resized() override
    {
        auto r = getLocalBounds().reduced(8, 4);
        const int fixedW = 56 + 8 + 28 + 4 + 4 + 28 + 14 + 70 + 6 + 86;      // everything but the name box
        const int nameW = juce::jlimit(160, 320, r.getWidth() - fixedW - 40);
        const int total = fixedW + nameW;
        auto c = r.withSizeKeepingCentre(juce::jmin(total, r.getWidth()), r.getHeight());
        labelArea = c.removeFromLeft(56); c.removeFromLeft(8);
        prev.setBounds(c.removeFromLeft(28)); c.removeFromLeft(4);
        nameBox.setBounds(c.removeFromLeft(nameW)); c.removeFromLeft(4);
        next.setBounds(c.removeFromLeft(28)); c.removeFromLeft(14);
        save.setBounds(c.removeFromLeft(70)); c.removeFromLeft(6);
        saveAs.setBounds(c.removeFromLeft(86));
    }

private:
    // The preset name with a drop-down arrow; click = menu.
    struct NameBox : juce::Component, juce::SettableTooltipClient
    {
        juce::String text; bool modified = false;
        std::function<void()> onClick;
        void paint(juce::Graphics& g) override
        {
            auto r = getLocalBounds().toFloat().reduced(0.5f);
            g.setColour(juce::Colour(isMouseOver() ? 0xff16181a : 0xff0f1011)); g.fillRoundedRectangle(r, 4.0f);
            g.setColour(juce::Colour(0xff4a4f55)); g.drawRoundedRectangle(r, 4.0f, 1.0f);
            auto t = r.reduced(10.0f, 0.0f);
            auto arrow = t.removeFromRight(12.0f);
            juce::Path p; const float cx = arrow.getCentreX(), cy = arrow.getCentreY();
            p.addTriangle(cx - 5.0f, cy - 2.5f, cx + 5.0f, cy - 2.5f, cx, cy + 3.5f);
            g.setColour(juce::Colours::white.withAlpha(0.6f)); g.fillPath(p);
            g.setColour(juce::Colour(0xffe8a33a));
            g.setFont(juce::FontOptions(14.0f, juce::Font::bold));
            g.drawFittedText(text + (modified ? " *" : ""), t.toNearestInt(), juce::Justification::centredLeft, 1);
        }
        void mouseDown(const juce::MouseEvent&) override { if (onClick) onClick(); }
        void mouseEnter(const juce::MouseEvent&) override { repaint(); }
        void mouseExit(const juce::MouseEvent&) override { repaint(); }
    };

    PresetManager& mgr;
    juce::TextButton prev { "<" }, next { ">" }, save { "Save" }, saveAs { "Save As..." };
    NameBox nameBox;
    juce::Rectangle<int> labelArea;

    void timerCallback() override { refresh(); }      // catches knob moves, pedal moves, session loads
    void refresh()
    {
        const auto name = mgr.displayName();
        const bool mod = mgr.isModified();
        if (name != nameBox.text || mod != nameBox.modified)
        {
            nameBox.text = name; nameBox.modified = mod;
            nameBox.repaint();
        }
    }

    juce::String suggestedName() const { return mgr.isUserPreset() ? mgr.currentName() : juce::String(); }

    void saveCurrent()
    {
        if (! mgr.isUserPreset())       // the default board / unsaved: ask for a name
            return askName("Save Preset", "Name for this preset:", {}, [this](const juce::String& n) { saveAsName(n); });
        report(mgr.save(mgr.currentName()));
    }
    void saveAsName(const juce::String& raw)
    {
        const auto name = PresetManager::legalName(raw);
        if (name.isNotEmpty() && PresetManager::fileFor(name).exists() && name != mgr.currentName())
        {
            confirm("Replace Preset", "A preset called \"" + name + "\" already exists. Replace it?", "Replace",
                    [this, name] { report(mgr.save(name)); });
            return;
        }
        report(mgr.save(name));
    }

    void showMenu()
    {
        enum { idDefault = 1, idSave, idSaveAs, idRename, idDelete, idFolder, idFirstPreset = 100 };
        auto files = mgr.list();
        const auto current = mgr.currentFile();
        juce::PopupMenu m;
        m.addSectionHeader("User presets");
        if (files.isEmpty()) m.addItem(-1, "(none saved yet)", false);
        for (int i = 0; i < files.size(); ++i)
            m.addItem(idFirstPreset + i, files[i].getFileNameWithoutExtension(), true, files[i] == current);
        m.addSeparator();
        m.addItem(idDefault, PresetManager::defaultName, true, ! mgr.isUserPreset() && mgr.displayName() == PresetManager::defaultName);
        m.addSeparator();
        m.addItem(idSave, "Save", true);
        m.addItem(idSaveAs, "Save As...", true);
        m.addItem(idRename, "Rename...", mgr.isUserPreset());
        m.addItem(idDelete, "Delete", mgr.isUserPreset());
        m.addSeparator();
        m.addItem(idFolder, "Show Presets Folder");

        juce::Component::SafePointer<PresetBar> safe(this);
        m.showMenuAsync(juce::PopupMenu::Options().withTargetComponent(&nameBox).withMinimumWidth(nameBox.getWidth()),
            [safe, files](int r)
            {
                if (safe == nullptr || r <= 0) return;
                auto& self = *safe;
                if (r >= idFirstPreset && r - idFirstPreset < files.size())
                {
                    const auto f = files[r - idFirstPreset];
                    if (! self.mgr.load(f)) self.message("Couldn't load " + f.getFileName() + " (missing or not a preset file).");
                }
                else if (r == idDefault) self.mgr.loadDefault();
                else if (r == idSave)    self.saveCurrent();
                else if (r == idSaveAs)  self.saveAs.triggerClick();
                else if (r == idRename)
                    self.askName("Rename Preset", "New name:", self.mgr.currentName(), [&self](const juce::String& n)
                                 { self.report(self.mgr.renameCurrent(n)); });
                else if (r == idDelete)
                    self.confirm("Delete Preset", "Delete \"" + self.mgr.currentName() + "\"? This can't be undone.", "Delete",
                                 [&self] { if (! self.mgr.deleteCurrent()) self.message("Couldn't delete the preset file."); self.refresh(); });
                else if (r == idFolder)
                {
                    auto dir = PresetManager::folder();
                    dir.createDirectory();
                    dir.startAsProcess();       // opens it in Explorer / Finder
                }
                self.refresh();
            });
    }

    // ---- small async dialogs (safe in plugin hosts: no modal loops) ----
    void askName(const juce::String& title, const juce::String& prompt, const juce::String& initial,
                 std::function<void(const juce::String&)> onOk)
    {
        auto* w = new juce::AlertWindow(title, prompt, juce::MessageBoxIconType::NoIcon, this);
        w->addTextEditor("name", initial);
        w->addButton("OK", 1, juce::KeyPress(juce::KeyPress::returnKey));
        w->addButton("Cancel", 0, juce::KeyPress(juce::KeyPress::escapeKey));
        w->setAlwaysOnTop(true);
        juce::Component::SafePointer<PresetBar> safe(this);
        w->enterModalState(true, juce::ModalCallbackFunction::create([safe, w, onOk](int r)
        {
            if (r == 1 && safe != nullptr) onOk(w->getTextEditorContents("name"));
        }), true);
        if (auto* ed = w->getTextEditor("name")) { ed->grabKeyboardFocus(); ed->selectAll(); }
    }
    void confirm(const juce::String& title, const juce::String& text, const juce::String& okText, std::function<void()> onOk)
    {
        juce::Component::SafePointer<PresetBar> safe(this);
        juce::AlertWindow::showAsync(juce::MessageBoxOptions().withIconType(juce::MessageBoxIconType::QuestionIcon)
                                         .withTitle(title).withMessage(text).withButton(okText).withButton("Cancel")
                                         .withAssociatedComponent(this),
                                     [safe, onOk](int r) { if (r == 1 && safe != nullptr) { onOk(); safe->refresh(); } });
    }
    void message(const juce::String& text)
    {
        juce::AlertWindow::showAsync(juce::MessageBoxOptions().withIconType(juce::MessageBoxIconType::WarningIcon)
                                         .withTitle("Presets").withMessage(text).withButton("OK").withAssociatedComponent(this),
                                     nullptr);
    }
    void report(const juce::Result& r) { if (r.failed()) message(r.getErrorMessage()); refresh(); }
};
