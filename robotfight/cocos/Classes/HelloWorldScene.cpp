#include "HelloWorldScene.h"
#include "RobotFightCore.h"
#include "audio/include/AudioEngine.h"

#include <algorithm>
#include <cstdio>
#include <memory>
#include <string>
#include <vector>

USING_NS_CC;
using cocos2d::experimental::AudioEngine;

namespace {
using robotfight::Battle;
using robotfight::BattleOutcome;
using robotfight::Command;
using robotfight::LocalProfile;
using robotfight::PartStats;
using robotfight::RobotBuild;



void playOriginalSoundEvent(const std::string& eventName) {
    const auto soundData = FileUtils::getInstance()->getValueMapFromFile("original/SoundEvents.plist");
    const auto eventsIt = soundData.find("events");
    if (eventsIt == soundData.end()) return;
    const auto events = eventsIt->second.asValueMap();
    const auto eventIt = events.find(eventName);
    if (eventIt == events.end()) return;
    const auto event = eventIt->second.asValueMap();
    const auto tracksIt = event.find("localTracks");
    if (tracksIt == event.end()) return;

    float gain = 1.0f;
    const auto effectsIt = event.find("effects");
    if (effectsIt != event.end() && !effectsIt->second.asValueVector().empty()) {
        const auto effect = effectsIt->second.asValueVector().front().asValueMap();
        const auto gainIt = effect.find("gain");
        if (gainIt != effect.end()) gain = gainIt->second.asFloat();
    }
    const float volume = std::min(1.0f, std::max(0.0f, gain * 0.5f));
    for (const auto& track : tracksIt->second.asValueVector()) {
        const std::string file = "original/" + track.asString();
        if (FileUtils::getInstance()->isFileExist(file))
            AudioEngine::play2d(file, false, volume);
    }
}

Sprite* playOriginalEffect(Node* parent, const std::string& animationFile,
                          const Vec2& position, float scale, bool loop = false) {
    if (!parent) return nullptr;
    const std::string path = "original/" + animationFile;
    const auto config = FileUtils::getInstance()->getValueMapFromFile(path);
    if (config.empty()) return nullptr;

    const auto textureIt = config.find("texture");
    const auto fpsIt = config.find("fps");
    const auto animationsIt = config.find("animations");
    if (textureIt == config.end() || animationsIt == config.end()) return nullptr;

    const auto animations = animationsIt->second.asValueMap();
    const auto playIt = animations.find("PlayEffect");
    if (playIt == animations.end()) return nullptr;
    const auto play = playIt->second.asValueMap();
    const auto framesIt = play.find("frames");
    if (framesIt == play.end()) return nullptr;

    const std::string atlas = "original/" + textureIt->second.asString();
    SpriteFrameCache::getInstance()->addSpriteFramesWithFile(atlas);
    const int fps = fpsIt == config.end() ? 24 : std::max(1, fpsIt->second.asInt());
    Vector<SpriteFrame*> frames;
    for (const auto& frameValue : framesIt->second.asValueVector()) {
        const std::string spec = frameValue.asString();
        char pattern[256] = {};
        int first = 1, last = 1;
        if (std::sscanf(spec.c_str(), "%255[^,],%d,%d", pattern, &first, &last) != 3)
            continue;
        for (int index = first; index <= last; ++index) {
            const auto frameName = StringUtils::format(pattern, index);
            if (auto frame = SpriteFrameCache::getInstance()->getSpriteFrameByName(frameName))
                frames.pushBack(frame);
        }
    }
    if (frames.empty()) return nullptr;

    auto sprite = Sprite::createWithSpriteFrame(frames.front());
    if (!sprite) return nullptr;
    sprite->setPosition(position);
    sprite->setScale(scale);
    parent->addChild(sprite, 40);
    auto animation = Animation::createWithSpriteFrames(frames, 1.0f / fps);
    if (!animation) {
        sprite->removeFromParent();
        return nullptr;
    }
    if (loop) {
        sprite->runAction(RepeatForever::create(Animate::create(animation)));
    } else {
        sprite->runAction(Sequence::create(Animate::create(animation), RemoveSelf::create(), nullptr));
    }
    return sprite;
}

RobotBuild makeDataBuild(const std::string& name,
                          const std::array<std::string, 5>& ids, const std::string& batteryId = "0_0") {
    RobotBuild build;
    build.id = name;
    build.displayName = name;
    const auto catalog = FileUtils::getInstance()->getValueMapFromFile("original/RFPartsData.plist");
    const char* categories[] = {"Base", "Core", "Head", "FrontArm", "BackArm"};
    for (std::size_t i = 0; i < ids.size(); ++i) {
        PartStats stats{80, 12, 8, 100};
        auto category = catalog.find(categories[i]);
        if (category != catalog.end()) {
            const auto entries = category->second.asValueMap();
            auto found = entries.find(ids[i]);
            if (found != entries.end()) {
                const auto item = found->second.asValueMap();
                const float power = item.count("powerPoint") ? item.at("powerPoint").asFloat() : 20.0f;
                const float attack = item.count("baseAtk") ? item.at("baseAtk").asFloat() : 10.0f;
                float hpScale = 1.0f;
                if (item.count("hpMultiplier")) {
                    const auto hp = item.at("hpMultiplier").asValueMap();
                    if (hp.count("default")) hpScale = hp.at("default").asFloat();
                }
                stats.health = std::max(20, static_cast<int>(power * 3.0f + hpScale * 2.0f));
                stats.attack = std::max(1, static_cast<int>(attack + power * 0.15f));
                stats.defense = std::max(1, static_cast<int>(hpScale * 2.0f));
            }
        }
        build.parts[i] = stats;
    }
    auto batteries = catalog.find("Battery");
    if (batteries != catalog.end()) {
        const auto entries = batteries->second.asValueMap();
        auto found = entries.find(batteryId);
        if (found != entries.end()) {
            const auto item = found->second.asValueMap();
            const float capacity = item.count("mAh") ? item.at("mAh").asFloat() : 500.0f;
            build.parts[0].energy = 100 + static_cast<int>(capacity / 10.0f);
        }
    }
    return build;
}
}


Scene* HelloWorld::createScene() {
    return HelloWorld::create();
}

bool HelloWorld::init() {
    if (!Scene::init()) return false;
    const int menuMusicId = AudioEngine::play2d("original/intro_bgm.wav", true, 0.42f);

    const auto visible = Director::getInstance()->getVisibleSize();
    const auto origin = Director::getInstance()->getVisibleOrigin();
    const float w = visible.width;
    const float h = visible.height;

    // Original Toy Attack arena artwork is loaded from the recovered DCA resources.
    // Start in the recovered training arena artwork; stage selection swaps this
    // for the corresponding original full-scene thumbnail before a fight begins.
    auto arena = Sprite::create("original/scene_thumbnail_11.png");
    if (!arena) arena = Sprite::create("original/background_3_1.png");
    if (arena) {
        const auto textureSize = arena->getContentSize();
        const float scale = std::max(w / textureSize.width, h / textureSize.height);
        arena->setScale(scale);
        arena->setPosition(Vec2(w * 0.5f, h * 0.5f));
        addChild(arena, -3);
    }

    auto bg = DrawNode::create();
    bg->drawSolidRect(Vec2(0, 0), Vec2(w, h), Color4F(0.025f, 0.035f, 0.065f, 0.48f));
    bg->drawSolidRect(Vec2(0, h * 0.70f), Vec2(w, h), Color4F(0.055f, 0.085f, 0.13f, 0.36f));
    bg->drawSolidRect(Vec2(0, h * 0.16f), Vec2(w, h * 0.20f), Color4F(0.12f, 0.16f, 0.20f, 0.42f));
    addChild(bg, -2);

    auto title = Label::createWithSystemFont("TOY ATTACK  /  OFFLINE ARENA", "Arial", 26);
    title->setTextColor(Color4B(235, 242, 255, 255));
    title->setPosition(origin + Vec2(w * 0.5f, h - 28));
    addChild(title);

    auto playerBuild = makeDataBuild("PLAYER", {
        UserDefault::getInstance()->getStringForKey("rf.part.base", "2_0"),
        UserDefault::getInstance()->getStringForKey("rf.part.core", "1_0"),
        UserDefault::getInstance()->getStringForKey("rf.part.head", "3_5"),
        UserDefault::getInstance()->getStringForKey("rf.part.front", "0_0"),
        UserDefault::getInstance()->getStringForKey("rf.part.back", "0_3")
    }, UserDefault::getInstance()->getStringForKey("rf.part.battery", "0_0"));
    auto botBuild = makeDataBuild("TRAINING BOT", {"1_0", "1_0", "3_5", "0_0", "1_0"}, "0_1");
    auto battle = std::make_shared<Battle>(playerBuild, botBuild, 0x51A7u);

    // Original battle HUD components recovered from RFBattleLayer.ccb.
    if (auto hudLeft = Sprite::create("original/battle_player_info.png")) {
        hudLeft->setPosition(w * 0.25f, h * 0.91f);
        hudLeft->setScale(0.58f);
        addChild(hudLeft, 8);
    }
    if (auto hudRight = Sprite::create("original/battle_player_info.png")) {
        hudRight->setPosition(w * 0.75f, h * 0.91f);
        hudRight->setFlippedX(true);
        hudRight->setScale(0.58f);
        addChild(hudRight, 8);
    }
    if (auto timerFrame = Sprite::create("original/battle_timer.png")) {
        timerFrame->setPosition(w * 0.5f, h * 0.91f);
        timerFrame->setScale(0.55f);
        addChild(timerFrame, 9);
    }
    if (auto boostBar = Sprite::create("original/battle_boost_bar.png")) {
        boostBar->setPosition(w * 0.5f, h * 0.72f);
        boostBar->setScale(0.62f);
        addChild(boostBar, 8);
    }
    auto playerName = Label::createWithSystemFont("PLAYER", "Arial", 19);
    playerName->setPosition(w * 0.25f, h * 0.84f);
    playerName->setTextColor(Color4B(95, 210, 255, 255));
    addChild(playerName);

    auto botName = Label::createWithSystemFont("OPPONENT", "Arial", 19);
    botName->setPosition(w * 0.75f, h * 0.84f);
    botName->setTextColor(Color4B(255, 145, 105, 255));
    addChild(botName);

    // Per-part condition indicators mirror the original PLAYER / OPPONENT HUD.
    const char* partIconFiles[] = {
        "battle_robot_hp_base.png", "battle_robot_hp_core.png",
        "battle_robot_hp_head.png", "battle_robot_hp_armf.png",
        "battle_robot_hp_armb.png"
    };
    auto makePartIndicators = [&](float centerX, float y) {
        std::array<Sprite*, 5> indicators{};
        for (int i = 0; i < 5; ++i) {
            auto icon = Sprite::create(std::string("original/") + partIconFiles[i]);
            if (icon) {
                icon->setPosition(centerX + (i - 2) * 27.0f, y);
                icon->setScale(0.62f);
                addChild(icon, 15);
            }
            indicators[i] = icon;
        }
        return indicators;
    };
    auto playerPartIndicators = makePartIndicators(w * 0.25f, h * 0.795f);
    auto opponentPartIndicators = makePartIndicators(w * 0.75f, h * 0.795f);

    auto battleEvent = Label::createWithSystemFont("", "Arial-BOLD", 30);
    battleEvent->setTextColor(Color4B(255, 190, 65, 255));
    battleEvent->setPosition(w * 0.5f, h * 0.67f);
    battleEvent->setOpacity(0);
    addChild(battleEvent, 80);

    // Resolve each robot's appearance independently. The opponent must use its own
    // recovered part IDs rather than accidentally mirroring the player's loadout.
    const auto readPlayerPartIds = []() {
        return std::array<std::string, 5>{{
            UserDefault::getInstance()->getStringForKey("rf.part.base", "2_0"),
            UserDefault::getInstance()->getStringForKey("rf.part.core", "1_0"),
            UserDefault::getInstance()->getStringForKey("rf.part.head", "3_5"),
            UserDefault::getInstance()->getStringForKey("rf.part.front", "0_0"),
            UserDefault::getInstance()->getStringForKey("rf.part.back", "0_3")
        }};
    };
    const std::array<std::string, 5> botPartIds = {{"1_0", "1_0", "3_5", "0_0", "1_0"}};
    const auto readPlayerBatteryId = []() {
        return UserDefault::getInstance()->getStringForKey("rf.part.battery", "0_0");
    };
    const std::string botBatteryId = "0_1";

    // Prefer original Toy Attack component art. The diagnostic fallback is used
    // only when an individual original sprite cannot be loaded.
    auto makeRobotView = [&](float x, float y, bool enemy,
                             const std::array<std::string, 5>& partIds,
                             const std::string& batteryId) -> Node* {
        auto robot = Node::create();
        const auto batteryTextureId = batteryId.substr(batteryId.find_last_of('_') + 1);
        const struct PartPlacement { std::string file; Vec2 position; float scale; } parts[] = {
            {(std::string("original/base_") + partIds[0] + ".png").c_str(), Vec2(0, -42), 0.72f},
            {(std::string("original/core_") + partIds[1] + ".png").c_str(), Vec2(0, 4), 0.72f},
            {(std::string("original/head_") + partIds[2] + ".png").c_str(), Vec2(0, 52), 0.72f},
            {(std::string("original/arm_b_") + partIds[4] + ".png").c_str(), Vec2(-61, 4), 0.62f},
            {(std::string("original/arm_f_") + partIds[3] + ".png").c_str(), Vec2(61, 4), 0.62f},
            {(std::string("original/battery_1_") + batteryTextureId + ".png").c_str(), Vec2(34, -62), 0.34f},
        };
        int loaded = 0;
        for (const auto& part : parts) {
            if (auto sprite = Sprite::create(part.file)) {
                sprite->setPosition(part.position);
                sprite->setScale(part.scale);
                if (enemy) sprite->setFlippedX(true);
                robot->addChild(sprite);
                ++loaded;
            }
        }
        if (loaded < 5) {
            robot->removeAllChildren();
            auto fallback = DrawNode::create();
            const auto body = enemy ? Color4F(0.72f, 0.25f, 0.16f, 1) : Color4F(0.10f, 0.55f, 0.78f, 1);
            const auto head = enemy ? Color4F(0.90f, 0.42f, 0.22f, 1) : Color4F(0.15f, 0.72f, 0.92f, 1);
            fallback->drawSolidRect(Vec2(-42, -28), Vec2(42, 28), body);
            fallback->drawSolidRect(Vec2(-25, 28), Vec2(25, 65), head);
            fallback->drawSolidCircle(Vec2(-12, 47), 5, 0, 16, Color4F::WHITE);
            fallback->drawSolidCircle(Vec2(12, 47), 5, 0, 16, Color4F::WHITE);
            robot->addChild(fallback);
        }
        robot->setPosition(x, y);
        return robot;
    };
    auto playerRobot = std::make_shared<Node*>(makeRobotView(w * 0.25f, h * 0.55f, false, readPlayerPartIds(), readPlayerBatteryId()));
    addChild(*playerRobot);
    auto botRobot = std::make_shared<Node*>(makeRobotView(w * 0.75f, h * 0.55f, true, botPartIds, botBatteryId));
    addChild(*botRobot);


    auto statusRef = std::make_shared<Label*>(nullptr);

    // Garage: cycle through original recovered part identifiers and persist each choice.
    auto openGarage = [=]() {
        playOriginalSoundEvent("press");
        auto panel = Node::create();
        addChild(panel, 300);
        if (auto backdrop = Sprite::create("original/editor_BG_tablet_01.png")) {
            const auto size = backdrop->getContentSize();
            backdrop->setScale(std::max(w / size.width, h / size.height));
            backdrop->setPosition(w * 0.5f, h * 0.5f);
            panel->addChild(backdrop, -2);
        }
        auto shade = DrawNode::create();
        shade->drawSolidRect(Vec2(0, 0), Vec2(w, h), Color4F(0.005f, 0.025f, 0.055f, 0.42f));
        panel->addChild(shade, -1);
        if (auto header = Sprite::create("original/ui_header.png")) {
            header->setPosition(w * 0.5f, h * 0.88f);
            header->setScale(0.95f);
            panel->addChild(header, 1);
        }
        auto heading = Label::createWithSystemFont("ROBOT LAB  /  PARTS", "Arial-BOLD", 27);
        heading->setPosition(w * 0.5f, h * 0.88f);
        heading->setTextColor(Color4B(110, 220, 255, 255));
        panel->addChild(heading);
        auto garageRobot = std::make_shared<Node*>(makeRobotView(w * 0.84f, h * 0.48f, false, readPlayerPartIds(), readPlayerBatteryId()));
        panel->addChild(*garageRobot, 5);

        const auto garageCatalog =
            FileUtils::getInstance()->getValueMapFromFile("original/RFPartsData.plist");
        struct Slot {
            const char* title;
            const char* key;
            const char* category;
            const char* prefix;
            const char* saveKey;
        };
        const Slot slots[] = {
            {"BASE", "base", "Base", "base_", "rf.part.base"},
            {"CORE", "core", "Core", "core_", "rf.part.core"},
            {"HEAD", "head", "Head", "head_", "rf.part.head"},
            {"BACK ARM", "back", "BackArm", "arm_b_", "rf.part.back"},
            {"FRONT ARM", "front", "FrontArm", "arm_f_", "rf.part.front"},
            {"BATTERY", "battery", "Battery", "battery_1_", "rf.part.battery"}
        };
        for (int i = 0; i < 6; ++i) {
            const float y = h * 0.75f - i * h * 0.095f;
            if (auto rowPanel = Sprite::create("original/editor_stats_panel.png")) {
                rowPanel->setPosition(w * 0.54f, y);
                rowPanel->setScale(0.18f);
                rowPanel->setOpacity(205);
                panel->addChild(rowPanel, 1);
            }
            auto name = Label::createWithSystemFont(slots[i].title, "Arial", 18);
            name->setAnchorPoint(Vec2(1, 0.5f));
            name->setPosition(w * 0.36f, y);
            name->setTextColor(Color4B(215, 230, 245, 255));
            panel->addChild(name);
            const auto slot = slots[i];
            auto current = Label::createWithSystemFont(
                UserDefault::getInstance()->getStringForKey(slot.saveKey,
                    std::string(slot.key) == "base" ? "2_0" :
                    std::string(slot.key) == "core" ? "1_0" :
                    std::string(slot.key) == "head" ? "3_5" :
                    std::string(slot.key) == "back" ? "0_3" :
                    std::string(slot.key) == "battery" ? "0_0" : "0_0"),
                "Arial", 19);
            current->setPosition(w * 0.56f, y);
            current->setTextColor(Color4B(255, 205, 95, 255));
            panel->addChild(current);

            std::vector<std::string> choices;
            const auto categoryIt = garageCatalog.find(slot.category);
            if (categoryIt != garageCatalog.end()) {
                for (const auto& entry : categoryIt->second.asValueMap()) {
                    const auto& partId = entry.first;
                    if (partId == "dummy") continue;
                    std::string imageName;
                    if (std::string(slot.key) == "battery") {
                        const auto separator = partId.find_last_of('_');
                        const auto textureId = separator == std::string::npos
                            ? partId : partId.substr(separator + 1);
                        imageName = std::string("original/") + slot.prefix + textureId + ".png";
                    } else {
                        imageName = std::string("original/") + slot.prefix + partId + ".png";
                    }
                    if (FileUtils::getInstance()->isFileExist(imageName))
                        choices.push_back(partId);
                }
            }
            if (choices.empty()) {
                choices = std::string(slot.key) == "battery"
                    ? std::vector<std::string>{"0_0", "0_1", "0_2"}
                    : std::vector<std::string>{"0_0", "1_0", "2_0", "3_5"};
            }
            auto change = [=](int direction) {
                auto value = UserDefault::getInstance()->getStringForKey(slot.saveKey, current->getString());
                auto it = std::find(choices.begin(), choices.end(), value);
                int index = it == choices.end() ? 0 : static_cast<int>(it - choices.begin());
                index = (index + direction + static_cast<int>(choices.size())) % static_cast<int>(choices.size());
                value = choices[index];
                UserDefault::getInstance()->setStringForKey(slot.saveKey, value);
                UserDefault::getInstance()->flush();
                current->setString(value);
                if (*playerRobot) (*playerRobot)->removeFromParent();
                *playerRobot = makeRobotView(w * 0.25f, h * 0.55f, false, readPlayerPartIds(), readPlayerBatteryId());
                addChild(*playerRobot, 2);
                if (*garageRobot) (*garageRobot)->removeFromParent();
                *garageRobot = makeRobotView(w * 0.84f, h * 0.48f, false, readPlayerPartIds(), readPlayerBatteryId());
                panel->addChild(*garageRobot, 5);
            };
            auto leftLabel = Label::createWithSystemFont("<", "Arial", 24);
            auto rightLabel = Label::createWithSystemFont(">", "Arial", 24);
            auto left = MenuItemLabel::create(leftLabel, [=](Ref*) { change(-1); });
            auto right = MenuItemLabel::create(rightLabel, [=](Ref*) { change(1); });
            left->setPosition(w * 0.43f, y);
            right->setPosition(w * 0.70f, y);
            auto arrows = Menu::create(left, right, nullptr);
            arrows->setPosition(Vec2::ZERO);
            panel->addChild(arrows);
        }
        auto closeLabel = Label::createWithSystemFont("BACK", "Arial", 20);
        auto close = MenuItemLabel::create(closeLabel, [=](Ref*) { panel->removeFromParent(); });
        close->setPosition(w * 0.5f, h * 0.10f);
        auto closeMenu = Menu::create(close, nullptr);
        closeMenu->setPosition(Vec2::ZERO);
        panel->addChild(closeMenu);
    };

    auto openStages = [=]() {
        auto panel = Node::create();
        addChild(panel, 300);
        if (auto backdrop = Sprite::create("original/editor_BG_tablet_02.png")) {
            const auto size = backdrop->getContentSize();
            backdrop->setScale(std::max(w / size.width, h / size.height));
            backdrop->setPosition(w * 0.5f, h * 0.5f);
            panel->addChild(backdrop, -2);
        }
        auto shade = DrawNode::create();
        shade->drawSolidRect(Vec2(0, 0), Vec2(w, h), Color4F(0.005f, 0.025f, 0.055f, 0.42f));
        panel->addChild(shade, -1);
        if (auto header = Sprite::create("original/ui_header.png")) {
            header->setPosition(w * 0.5f, h * 0.88f);
            header->setScale(0.95f);
            panel->addChild(header, 1);
        }
        auto heading = Label::createWithSystemFont("SELECT ARENA", "Arial-BOLD", 27);
        heading->setPosition(w * 0.5f, h * 0.88f);
        heading->setTextColor(Color4B(110, 220, 255, 255));
        panel->addChild(heading);
        const char* stageIds[] = {"scene_11","scene_0","scene_1","scene_3","scene_13","scene_19"};
        const char* stageNames[] = {"TRAINING","SCRAP YARD","FACTORY","ROOFTOPS","CORE DROP","FINAL PIT"};
        for (int i = 0; i < 6; ++i) {
            const float x = w * (0.20f + (i % 3) * 0.30f);
            const float y = h * (0.62f - (i / 3) * 0.32f);
            if (auto card = Sprite::create("original/story_level_panel.png")) {
                card->setPosition(x, y);
                card->setScale(0.22f);
                panel->addChild(card, 0);
            }
            auto preview = Sprite::create(std::string("original/scene_thumbnail_") +
                                           std::string(stageIds[i]).substr(6) + ".png");
            if (preview) {
                preview->setPosition(x, y + h * 0.045f);
                preview->setScale(std::min(0.085f, w * 0.105f / preview->getContentSize().width));
                panel->addChild(preview, 1);
            }
            const std::string stageName = stageNames[i];
            const std::string stageId = stageIds[i];
            auto label = Label::createWithSystemFont(stageName, "Arial", 16);
            auto item = MenuItemLabel::create(label, [=](Ref*) {
                UserDefault::getInstance()->setStringForKey("rf.stage", stageId);
                UserDefault::getInstance()->flush();
                if (arena) {
                    const std::string texturePath = std::string("original/scene_thumbnail_") +
                                                    stageId.substr(6) + ".png";
                    if (auto texture = Director::getInstance()->getTextureCache()->addImage(texturePath)) {
                        arena->setTexture(texture);
                        arena->setTextureRect(Rect(0, 0, texture->getContentSize().width,
                                                   texture->getContentSize().height));
                        arena->setScale(std::max(w / texture->getContentSize().width,
                                                 h / texture->getContentSize().height));
                        arena->setPosition(w * 0.5f, h * 0.5f);
                    }
                }
                if (*statusRef) (*statusRef)->setString(std::string("ARENA SELECTED: ") + stageName + "  |  READY");
                panel->removeFromParent();
            });
            item->setPosition(x, y - h * 0.055f);
            auto menu = Menu::create(item, nullptr);
            menu->setPosition(Vec2::ZERO);
            panel->addChild(menu);
        }
        auto closeLabel = Label::createWithSystemFont("BACK", "Arial", 20);
        auto close = MenuItemLabel::create(closeLabel, [=](Ref*) { panel->removeFromParent(); });
        close->setPosition(w * 0.5f, h * 0.08f);
        auto closeMenu = Menu::create(close, nullptr);
        closeMenu->setPosition(Vec2::ZERO);
        panel->addChild(closeMenu);
    };

    auto garageLabel = Label::createWithSystemFont("ROBOT LAB", "Arial", 16);
    auto garageItem = MenuItemLabel::create(garageLabel, [=](Ref*) { openGarage(); });
    garageItem->setPosition(w * 0.34f, h - 62);
    auto stagesLabel = Label::createWithSystemFont("STAGES", "Arial", 16);
    auto stagesItem = MenuItemLabel::create(stagesLabel, [=](Ref*) { openStages(); });
    stagesItem->setPosition(w * 0.51f, h - 62);
    auto navigation = Menu::create(garageItem, stagesItem, nullptr);
    navigation->setPosition(Vec2::ZERO);
    addChild(navigation, 10);

    auto coins = Label::createWithSystemFont("", "Arial", 17);
    coins->setAnchorPoint(Vec2(1, 0.5f));
    coins->setPosition(w - 18, h - 28);
    coins->setTextColor(Color4B(255, 215, 90, 255));
    addChild(coins);

    auto playerHp = Label::createWithSystemFont("", "Arial", 16);
    playerHp->setPosition(w * 0.25f, h * 0.77f);
    addChild(playerHp);
    auto botHp = Label::createWithSystemFont("", "Arial", 16);
    botHp->setPosition(w * 0.75f, h * 0.77f);
    addChild(botHp);

    auto status = Label::createWithSystemFont("Choose your move", "Arial", 18);
    status->setPosition(w * 0.5f, h * 0.32f);
    status->setTextColor(Color4B(230, 235, 245, 255));
    addChild(status);
    *statusRef = status;

    auto refresh = [=]() {
        playerHp->setString(StringUtils::format("HP %d   ENERGY %d",
            battle->playerTotalHp(), battle->playerState().energy));
        botHp->setString(StringUtils::format("HP %d   ENERGY %d",
            battle->botTotalHp(), battle->botState().energy));
        coins->setString(StringUtils::format("COINS  %d", LocalProfile::coins()));

        const auto updateParts = [](const std::array<Sprite*, 5>& cells,
                                    const robotfight::RobotState& state,
                                    const RobotBuild& build) {
            for (std::size_t i = 0; i < cells.size(); ++i) {
                if (!cells[i]) continue;
                const float ratio = static_cast<float>(std::max(0, state.hp[i])) /
                    static_cast<float>(std::max(1, build.parts[i].health));
                const Color3B tint = ratio <= 0.0f ? Color3B(75, 82, 92) :
                    ratio < 0.25f ? Color3B(235, 70, 55) :
                    ratio < 0.60f ? Color3B(255, 178, 55) :
                                    Color3B(95, 225, 190);
                cells[i]->setColor(tint);
                cells[i]->setOpacity(ratio <= 0.0f ? 100 : 255);
            }
        };
        updateParts(playerPartIndicators, battle->playerState(), playerBuild);
        updateParts(opponentPartIndicators, battle->botState(), botBuild);
    };
    refresh();

    auto makeButton = [&](const std::string& text, Command command, float x) {
        auto label = Label::createWithSystemFont(text, "Arial", 18);
        label->setTextColor(Color4B(255, 255, 255, 255));
        auto item = MenuItemLabel::create(label, [=](Ref*) {
            if (battle->outcome() != BattleOutcome::Ongoing) return;
            const int playerHeadBefore = battle->playerState().hp[2];
            const int opponentHeadBefore = battle->botState().hp[2];
            const auto result = battle->step(command);
            const bool playerHeadDestroyed = playerHeadBefore > 0 && battle->playerState().hp[2] <= 0;
            const bool opponentHeadDestroyed = opponentHeadBefore > 0 && battle->botState().hp[2] <= 0;
            if (playerHeadDestroyed || opponentHeadDestroyed) {
                battleEvent->stopAllActions();
                battleEvent->setString("HEAD DESTROYED");
                battleEvent->setOpacity(255);
                battleEvent->setScale(1.0f);
                battleEvent->runAction(Sequence::create(
                    ScaleTo::create(0.12f, 1.18f),
                    DelayTime::create(0.85f),
                    FadeOut::create(0.28f), nullptr));
                playOriginalSoundEvent("partsBroken");
            }
            if (result.playerDamage > 0) {
                (*playerRobot)->runAction(Sequence::create(
                    MoveBy::create(0.10f, Vec2(24, 0)),
                    MoveBy::create(0.14f, Vec2(-24, 0)), nullptr));
                (*botRobot)->runAction(Sequence::create(
                    MoveBy::create(0.06f, Vec2(9, 0)),
                    MoveBy::create(0.10f, Vec2(-9, 0)), nullptr));
                playOriginalEffect(this, "hit_ef1_default_Anim.plist", Vec2(w * 0.75f, h * 0.55f), 1.0f);
            }
            if (result.botDamage > 0) {
                (*botRobot)->runAction(Sequence::create(
                    MoveBy::create(0.10f, Vec2(-24, 0)),
                    MoveBy::create(0.14f, Vec2(24, 0)), nullptr));
                (*playerRobot)->runAction(Sequence::create(
                    MoveBy::create(0.06f, Vec2(-9, 0)),
                    MoveBy::create(0.10f, Vec2(9, 0)), nullptr));
                playOriginalEffect(this, "hit_ef2_default_Anim.plist", Vec2(w * 0.25f, h * 0.55f), 1.0f);
            }
            if (command == Command::Boost)
                playOriginalEffect(this, "boost_ef1_default_Anim.plist",
                                   (*playerRobot)->getPosition() + Vec2(-25, -48), 1.0f);
            if (command == Command::HeavyStrike)
                playOriginalSoundEvent("onHitSuper1");
            else if (command != Command::Guard)
                playOriginalSoundEvent("onHitNormal1");
            status->setString(StringUtils::format("YOU: %s   BOT: %s",
                command == Command::Strike ? "STRIKE" :
                command == Command::HeavyStrike ? "HEAVY" :
                command == Command::Boost ? "BOOST" : "GUARD",
                result.botCommand == Command::Strike ? "STRIKE" :
                result.botCommand == Command::HeavyStrike ? "HEAVY" :
                result.botCommand == Command::Boost ? "BOOST" : "GUARD"));
            if (result.outcome == BattleOutcome::PlayerWin) {
                LocalProfile::recordResult(result.outcome);
                status->setString("VICTORY  +2,000 COINS");
                playOriginalEffect(this, "explosion_ef1_default_Anim.plist",
                                   (*botRobot)->getPosition(), 1.8f);
                playOriginalSoundEvent("robotDestroy");
            } else if (result.outcome == BattleOutcome::BotWin) {
                LocalProfile::recordResult(result.outcome);
                status->setString("DEFEAT  -  NO COINS AWARDED");
                playOriginalEffect(this, "explosion_ef2_default_Anim.plist",
                                   (*playerRobot)->getPosition(), 1.8f);
                playOriginalSoundEvent("partsBroken");
            } else if (result.outcome == BattleOutcome::Draw) {
                status->setString("DRAW  -  NO COINS AWARDED");
            }
            refresh();
        });
        item->setPosition(x, h * 0.20f);
        item->setContentSize(Size(w * 0.17f, 48));
        return item;
    };

    // Original controller artwork frames the reconstructed offline controls.
    if (auto leftController = Sprite::create("original/battle_controller.png")) {
        leftController->setPosition(w * 0.12f, h * 0.30f);
        leftController->setScale(0.48f);
        addChild(leftController, 4);
    }
    if (auto rightController = Sprite::create("original/battle_controller.png")) {
        rightController->setPosition(w * 0.88f, h * 0.30f);
        rightController->setFlippedX(true);
        rightController->setScale(0.48f);
        addChild(rightController, 4);
    }
    if (auto direction = Sprite::create("original/battle_direction.png")) {
        direction->setPosition(w * 0.12f, h * 0.30f);
        direction->setScale(0.38f);
        addChild(direction, 5);
    }
    if (auto direction = Sprite::create("original/battle_direction.png")) {
        direction->setPosition(w * 0.88f, h * 0.30f);
        direction->setFlippedX(true);
        direction->setScale(0.38f);
        addChild(direction, 5);
    }

    auto menu = Menu::create(
        makeButton("STRIKE", Command::Strike, w * 0.20f),
        makeButton("HEAVY", Command::HeavyStrike, w * 0.40f),
        makeButton("BOOST", Command::Boost, w * 0.60f),
        makeButton("GUARD", Command::Guard, w * 0.80f),
        nullptr);
    menu->setPosition(Vec2::ZERO);
    addChild(menu, 5);

    auto note = Label::createWithSystemFont(
        "Native combat loop test  |  Local profile  |  ARM64", "Arial", 12);
    note->setTextColor(Color4B(115, 135, 160, 255));
    note->setPosition(w * 0.5f, 16);
    addChild(note);

    // Original-art home hub reconstructed from the recovered RFMainLayer resources.
    // The proprietary RCCB node graph is not decoded yet, so this is a native
    // layout using the exact original backgrounds, robot stand, tier and menu art.
    auto home = Node::create();
    addChild(home, 200);
    auto addHomeSprite = [=](const std::string& file, const Vec2& position,
                              float scale, int z = 0) -> Sprite* {
        auto sprite = Sprite::create("original/" + file + ".png");
        if (!sprite) return nullptr;
        sprite->setPosition(position);
        sprite->setScale(scale);
        home->addChild(sprite, z);
        return sprite;
    };
    if (auto homeArt = Sprite::create("original/1_common_bg_1.png")) {
        const auto size = homeArt->getContentSize();
        homeArt->setScale(std::max(w / size.width, h / size.height));
        homeArt->setPosition(w * 0.5f, h * 0.5f);
        home->addChild(homeArt, -5);
    }
    if (auto glow = addHomeSprite("mainmenu_robot_ef_1", Vec2(w * 0.29f, h * 0.43f), 1.05f, -2))
        glow->setOpacity(150);
    addHomeSprite("mainmeun_robotstand", Vec2(w * 0.29f, h * 0.20f), 0.72f, -1);
    auto homeRobot = makeRobotView(w * 0.29f, h * 0.43f, false,
                                   readPlayerPartIds(), readPlayerBatteryId());
    home->addChild(homeRobot, 1);
    addHomeSprite("mainmenu_player_info", Vec2(w * 0.22f, h * 0.84f), 0.53f, 2);
    addHomeSprite("mainmeun_tier", Vec2(w * 0.88f, h * 0.83f), 0.43f, 2);
    addHomeSprite("mainmenu_edit_btn", Vec2(w * 0.30f, h * 0.27f), 0.78f, 3);

    auto homeName = Label::createWithSystemFont("PLAYER", "Arial-BOLD", 18);
    homeName->setAnchorPoint(Vec2(0, 0.5f));
    homeName->setPosition(w * 0.095f, h * 0.865f);
    homeName->setTextColor(Color4B(225, 245, 255, 255));
    home->addChild(homeName, 4);
    auto homeRecord = Label::createWithSystemFont(
        StringUtils::format("WINS  %d     LOSSES  %d", LocalProfile::wins(), LocalProfile::losses()),
        "Arial", 13);
    homeRecord->setAnchorPoint(Vec2(0, 0.5f));
    homeRecord->setPosition(w * 0.095f, h * 0.815f);
    homeRecord->setTextColor(Color4B(135, 220, 245, 255));
    home->addChild(homeRecord, 4);
    auto homeTier = Label::createWithSystemFont("TIER  1", "Arial-BOLD", 17);
    homeTier->setPosition(w * 0.88f, h * 0.68f);
    homeTier->setTextColor(Color4B(255, 225, 135, 255));
    home->addChild(homeTier, 4);

    // The original main layer's fight console and menu buttons are reused as
    // visual controls rather than replacing the game with generic text buttons.
    addHomeSprite("fight_scene", Vec2(w * 0.73f, h * 0.43f), 0.57f, 0);
    addHomeSprite("fight_stand", Vec2(w * 0.73f, h * 0.22f), 0.43f, 1);
    auto fightCaption = Label::createWithSystemFont("FIGHT", "Arial-BOLD", 30);
    fightCaption->setTextColor(Color4B(255, 225, 155, 255));
    fightCaption->setPosition(w * 0.73f, h * 0.44f);
    home->addChild(fightCaption, 5);
    auto homeButtonArt = [=](float x, float y) {
        auto art = Sprite::create("original/btn_menu_top.png");
        if (!art) return;
        art->setPosition(x, y);
        art->setScale(0.60f);
        home->addChild(art, 2);
    };
    homeButtonArt(w * 0.48f, h * 0.13f);
    homeButtonArt(w * 0.68f, h * 0.13f);
    homeButtonArt(w * 0.86f, h * 0.13f);

    auto infoPanel = [=](const std::string& headingText, const std::string& bodyText) {
        auto panel = Node::create();
        addChild(panel, 250);
        auto dim = DrawNode::create();
        dim->drawSolidRect(Vec2(0, 0), Vec2(w, h), Color4F(0.01f, 0.02f, 0.04f, 0.94f));
        panel->addChild(dim);
        auto heading = Label::createWithSystemFont(headingText, "Arial", 26);
        heading->setPosition(w * 0.5f, h * 0.72f);
        heading->setTextColor(Color4B(110, 220, 255, 255));
        panel->addChild(heading);
        auto body = Label::createWithSystemFont(bodyText, "Arial", 19);
        body->setDimensions(w * 0.72f, h * 0.34f);
        body->setAlignment(TextHAlignment::CENTER, TextVAlignment::CENTER);
        body->setPosition(w * 0.5f, h * 0.47f);
        body->setTextColor(Color4B(225, 235, 245, 255));
        panel->addChild(body);
        auto closeLabel = Label::createWithSystemFont("BACK", "Arial", 20);
        auto close = MenuItemLabel::create(closeLabel, [=](Ref*) { panel->removeFromParent(); });
        close->setPosition(w * 0.5f, h * 0.16f);
        auto menu = Menu::create(close, nullptr);
        menu->setPosition(Vec2::ZERO);
        panel->addChild(menu);
    };

    auto fightLabel = Label::createWithSystemFont("FIGHT", "Arial", 24);
    auto fightItem = MenuItemLabel::create(fightLabel, [=](Ref*) {
        AudioEngine::play2d("original/sfx_btn_press.ogg");
        AudioEngine::play2d("original/sfx_battle_startBell.ogg");
        if (menuMusicId != AudioEngine::INVALID_AUDIO_ID) AudioEngine::stop(menuMusicId);
        AudioEngine::play2d("original/bgm_scene_battleFight.wav", true, 0.42f);
        home->removeFromParent();
    });
    fightItem->setPosition(w * 0.73f, h * 0.43f);
    auto labLabel = Label::createWithSystemFont("ROBOT LAB", "Arial", 20);
    auto labItem = MenuItemLabel::create(labLabel, [=](Ref*) { openGarage(); });
    labItem->setPosition(w * 0.30f, h * 0.27f);
    auto stageLabel = Label::createWithSystemFont("STAGES", "Arial", 20);
    auto stageItem = MenuItemLabel::create(stageLabel, [=](Ref*) { openStages(); });
    stageItem->setPosition(w * 0.48f, h * 0.13f);
    auto profileLabel = Label::createWithSystemFont("PROFILE", "Arial", 17);
    auto profileItem = MenuItemLabel::create(profileLabel, [=](Ref*) {
        infoPanel("PILOT PROFILE", StringUtils::format("COINS  %d\\nWINS  %d\\nLOSSES  %d",
            LocalProfile::coins(), LocalProfile::wins(), LocalProfile::losses()));
    });
    profileItem->setPosition(w * 0.68f, h * 0.13f);
    auto questLabel = Label::createWithSystemFont("QUEST DATA", "Arial", 17);
    auto questItem = MenuItemLabel::create(questLabel, [=](Ref*) {
        const auto questData = FileUtils::getInstance()->getValueMapFromFile("original/RFQuestData.plist");
        std::size_t questCount = 0;
        std::size_t achievementGroups = 0;
        auto list = questData.find("QuestList");
        if (list != questData.end()) questCount = list->second.asValueVector().size();
        auto achievements = questData.find("AchievementsDict");
        if (achievements != questData.end()) achievementGroups = achievements->second.asValueMap().size();
        infoPanel("RECOVERED QUEST DATA", StringUtils::format("%d original quest entries\\n%zu achievement groups\\nQuest progression is still being rebuilt.",
            static_cast<int>(questCount), achievementGroups));
    });
    questItem->setPosition(w * 0.86f, h * 0.13f);
    auto homeMenu = Menu::create(fightItem, labItem, stageItem, profileItem, questItem, nullptr);
    homeMenu->setPosition(Vec2::ZERO);
    home->addChild(homeMenu);

    return true;
}
