#include "HelloWorldScene.h"
#include "RobotFightCore.h"

#include <memory>
#include <string>

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

    auto bg = DrawNode::create();
    bg->drawSolidRect(Vec2(0, 0), Vec2(w, h), Color4F(0.025f, 0.035f, 0.065f, 1));
    bg->drawSolidRect(Vec2(0, h * 0.70f), Vec2(w, h), Color4F(0.055f, 0.085f, 0.13f, 1));
    bg->drawSolidRect(Vec2(0, h * 0.16f), Vec2(w, h * 0.20f), Color4F(0.12f, 0.16f, 0.20f, 1));
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
        const struct PartPlacement { const char* file; Vec2 position; float scale; } parts[] = {
            {"original/base_2_0.png", Vec2(0, -42), 0.72f},
            {"original/core_1_0.png", Vec2(0, 4), 0.72f},
            {"original/head_0_0.png", Vec2(0, 52), 0.72f},
            {"original/arm_b_0_3.png", Vec2(-61, 4), 0.62f},
            {"original/arm_f_0_0.png", Vec2(61, 4), 0.62f},
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
    addChild(makeRobotView(w * 0.25f, h * 0.55f, false));
    addChild(makeRobotView(w * 0.75f, h * 0.55f, true));

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
