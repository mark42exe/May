#include "HelloWorldScene.h"
#include "RobotFightCore.h"

#include <memory>
#include <string>
#include <vector>

USING_NS_CC;

namespace {
using robotfight::Battle;
using robotfight::BattleOutcome;
using robotfight::Command;
using robotfight::LocalProfile;
using robotfight::PartStats;
using robotfight::RobotBuild;

RobotBuild makeBuild(const std::string& id, const std::string& name,
                     int hp, int attack, int defense) {
    RobotBuild build;
    build.id = id;
    build.displayName = name;
    for (auto& part : build.parts) part = PartStats{hp, attack, defense, 100};
    return build;
}
}


Scene* HelloWorld::createScene() {
    return HelloWorld::create();
}

bool HelloWorld::init() {
    if (!Scene::init()) return false;

    const auto visible = Director::getInstance()->getVisibleSize();
    const auto origin = Director::getInstance()->getVisibleOrigin();
    const float w = visible.width;
    const float h = visible.height;

    // Original Toy Attack arena artwork is loaded from the recovered DCA resources.
    if (auto arena = Sprite::create("original/background_3_1.png")) {
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

    auto playerBuild = makeBuild("player_local", "PLAYER", 100, 42, 28);
    auto botBuild = makeBuild("bot_training", "TRAINING BOT", 92, 38, 24);
    auto battle = std::make_shared<Battle>(playerBuild, botBuild, 0x51A7u);

    auto playerName = Label::createWithSystemFont("PLAYER", "Arial", 19);
    playerName->setPosition(w * 0.25f, h * 0.84f);
    playerName->setTextColor(Color4B(95, 210, 255, 255));
    addChild(playerName);

    auto botName = Label::createWithSystemFont("OPPONENT", "Arial", 19);
    botName->setPosition(w * 0.75f, h * 0.84f);
    botName->setTextColor(Color4B(255, 145, 105, 255));
    addChild(botName);

    // Prefer original Toy Attack component art when the optional asset pack is present.
    // The fallback remains a simple diagnostic silhouette until the full scene reader is ready.
    auto makeRobotView = [&](float x, float y, bool enemy) -> Node* {
        auto robot = Node::create();
        const struct PartPlacement { std::string file; Vec2 position; float scale; } parts[] = {
            {(std::string("original/base_") + UserDefault::getInstance()->getStringForKey("rf.part.base", "2_0") + ".png").c_str(), Vec2(0, -42), 0.72f},
            {(std::string("original/core_") + UserDefault::getInstance()->getStringForKey("rf.part.core", "1_0") + ".png").c_str(), Vec2(0, 4), 0.72f},
            {(std::string("original/head_") + UserDefault::getInstance()->getStringForKey("rf.part.head", "3_5") + ".png").c_str(), Vec2(0, 52), 0.72f},
            {(std::string("original/arm_b_") + UserDefault::getInstance()->getStringForKey("rf.part.back", "0_3") + ".png").c_str(), Vec2(-61, 4), 0.62f},
            {(std::string("original/arm_f_") + UserDefault::getInstance()->getStringForKey("rf.part.front", "0_0") + ".png").c_str(), Vec2(61, 4), 0.62f},
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
    auto playerRobot = std::make_shared<Node*>(makeRobotView(w * 0.25f, h * 0.55f, false));
    addChild(*playerRobot);
    addChild(makeRobotView(w * 0.75f, h * 0.55f, true));


    // Garage: cycle through original recovered part identifiers and persist each choice.
    auto openGarage = [=]() {
        auto panel = Node::create();
        addChild(panel, 100);
        auto shade = DrawNode::create();
        shade->drawSolidRect(Vec2(0, 0), Vec2(w, h), Color4F(0.015f, 0.025f, 0.05f, 0.96f));
        panel->addChild(shade);
        auto heading = Label::createWithSystemFont("ROBOT LAB  /  PARTS", "Arial", 27);
        heading->setPosition(w * 0.5f, h * 0.88f);
        heading->setTextColor(Color4B(110, 220, 255, 255));
        panel->addChild(heading);

        const std::vector<std::string> ids = {
            "0_0","0_1","0_2","0_3","0_4","0_5","0_6",
            "1_0","1_1","1_2","1_3","1_4","1_5","1_6",
            "2_0","2_1","2_2","2_3","2_4","2_5","2_6",
            "3_0","3_1","3_2","3_3","3_4","3_5","3_6","3_7","3_12"
        };
        struct Slot { const char* title; const char* key; const char* prefix; const char* saveKey; };
        const Slot slots[] = {
            {"BASE", "base", "base_", "rf.part.base"},
            {"CORE", "core", "core_", "rf.part.core"},
            {"HEAD", "head", "head_", "rf.part.head"},
            {"BACK ARM", "back", "arm_b_", "rf.part.back"},
            {"FRONT ARM", "front", "arm_f_", "rf.part.front"}
        };
        for (int i = 0; i < 5; ++i) {
            const float y = h * 0.73f - i * h * 0.115f;
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
                    std::string(slot.key) == "back" ? "0_3" : "0_0"),
                "Arial", 19);
            current->setPosition(w * 0.56f, y);
            current->setTextColor(Color4B(255, 205, 95, 255));
            panel->addChild(current);

            auto change = [=](int direction) {
                auto value = UserDefault::getInstance()->getStringForKey(slot.saveKey, current->getString());
                auto it = std::find(ids.begin(), ids.end(), value);
                int index = it == ids.end() ? 0 : static_cast<int>(it - ids.begin());
                index = (index + direction + static_cast<int>(ids.size())) % static_cast<int>(ids.size());
                value = ids[index];
                UserDefault::getInstance()->setStringForKey(slot.saveKey, value);
                UserDefault::getInstance()->flush();
                current->setString(value);
                if (*playerRobot) (*playerRobot)->removeFromParent();
                *playerRobot = makeRobotView(w * 0.25f, h * 0.55f, false);
                addChild(*playerRobot, 2);
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
        addChild(panel, 100);
        auto shade = DrawNode::create();
        shade->drawSolidRect(Vec2(0, 0), Vec2(w, h), Color4F(0.015f, 0.025f, 0.05f, 0.96f));
        panel->addChild(shade);
        auto heading = Label::createWithSystemFont("SELECT ARENA", "Arial", 27);
        heading->setPosition(w * 0.5f, h * 0.88f);
        heading->setTextColor(Color4B(110, 220, 255, 255));
        panel->addChild(heading);
        const char* stageIds[] = {"scene_11","scene_0","scene_1","scene_3","scene_13","scene_19"};
        const char* stageNames[] = {"TRAINING","SCRAP YARD","FACTORY","ROOFTOPS","CORE DROP","FINAL PIT"};
        for (int i = 0; i < 6; ++i) {
            const float x = w * (0.20f + (i % 3) * 0.30f);
            const float y = h * (0.62f - (i / 3) * 0.32f);
            auto preview = Sprite::create(std::string("original/scene_thumbnail_") +
                                           stageIds[i].substr(6) + ".png");
            if (preview) {
                preview->setPosition(x, y + h * 0.055f);
                preview->setScale(std::min(0.42f, w * 0.13f / preview->getContentSize().width));
                panel->addChild(preview);
            }
            auto label = Label::createWithSystemFont(stageNames[i], "Arial", 16);
            auto item = MenuItemLabel::create(label, [=](Ref*) {
                status->setString(std::string("ARENA SELECTED: ") + stageNames[i] + "  |  READY");
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

    auto refresh = [=]() {
        playerHp->setString(StringUtils::format("HP %d   ENERGY %d",
            battle->playerTotalHp(), battle->playerState().energy));
        botHp->setString(StringUtils::format("HP %d   ENERGY %d",
            battle->botTotalHp(), battle->botState().energy));
        coins->setString(StringUtils::format("COINS  %d", LocalProfile::coins()));
    };
    refresh();

    auto makeButton = [&](const std::string& text, Command command, float x) {
        auto label = Label::createWithSystemFont(text, "Arial", 18);
        label->setTextColor(Color4B(255, 255, 255, 255));
        auto item = MenuItemLabel::create(label, [=](Ref*) {
            if (battle->outcome() != BattleOutcome::Ongoing) return;
            const auto result = battle->step(command);
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
            } else if (result.outcome == BattleOutcome::BotWin) {
                LocalProfile::recordResult(result.outcome);
                status->setString("DEFEAT  -  NO COINS AWARDED");
            } else if (result.outcome == BattleOutcome::Draw) {
                status->setString("DRAW  -  NO COINS AWARDED");
            }
            refresh();
        });
        item->setPosition(x, h * 0.20f);
        item->setContentSize(Size(w * 0.17f, 48));
        return item;
    };

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

    return true;
}
