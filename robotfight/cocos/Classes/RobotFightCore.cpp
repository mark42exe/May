#include "RobotFightCore.h"

#include "cocos2d.h"
#include <algorithm>
#include <numeric>
#include <cstdio>

namespace robotfight {
namespace {
constexpr int kVictoryReward = 2000;
constexpr int kStartingEnergy = 100;
constexpr int kHeavyCost = 35;
constexpr int kBoostCost = 20;

int totalHealth(const RobotBuild& build) {
    int total = 0;
    for (const auto& part : build.parts) total += std::max(1, part.health);
    return total;
}

int totalAttack(const RobotBuild& build) {
    int total = 0;
    for (const auto& part : build.parts) total += std::max(0, part.attack);
    return total;
}

int totalDefense(const RobotBuild& build) {
    int total = 0;
    for (const auto& part : build.parts) total += std::max(0, part.defense);
    return total;
}

RobotState makeState(const RobotBuild& build) {
    RobotState state;
    for (std::size_t i = 0; i < state.hp.size(); ++i)
        state.hp[i] = std::max(1, build.parts[i].health);
    state.maxEnergy = std::max(kStartingEnergy, build.parts[0].energy);
    state.energy = state.maxEnergy;
    return state;
}

int boundedDamage(int raw, int defense, bool guarding) {
    const int reduced = std::max(1, raw - defense / 4);
    return guarding ? std::max(1, reduced / 2) : reduced;
}
}

Battle::Battle(const RobotBuild& player, const RobotBuild& bot, std::uint32_t seed)
    : playerBuild_(player), botBuild_(bot), player_(makeState(player)),
      bot_(makeState(bot)), rng_(seed ? seed : 0x9e3779b9u) {}

std::size_t Battle::weakestPart(const RobotState& state) {
    return static_cast<std::size_t>(std::distance(
        state.hp.begin(), std::min_element(state.hp.begin(), state.hp.end())));
}

int Battle::playerTotalHp() const {
    return std::accumulate(player_.hp.begin(), player_.hp.end(), 0);
}
int Battle::botTotalHp() const {
    return std::accumulate(bot_.hp.begin(), bot_.hp.end(), 0);
}

Command Battle::chooseBotCommand() {
    // Small deterministic xorshift generator keeps replays reproducible.
    rng_ ^= rng_ << 13; rng_ ^= rng_ >> 17; rng_ ^= rng_ << 5;
    const unsigned roll = rng_ % 100;
    if (bot_.energy >= kHeavyCost && roll < 32) return Command::HeavyStrike;
    if (bot_.energy >= kBoostCost && roll < 48) return Command::Boost;
    if (roll < 72) return Command::Strike;
    return Command::Guard;
}

int Battle::resolveDamage(const RobotBuild& attacker, const RobotState&,
                          const RobotBuild& defender, const RobotState&,
                          Command command, bool guarding) const {
    int power = totalAttack(attacker) / 5;
    if (command == Command::HeavyStrike) power = power * 3 / 2;
    if (command == Command::Boost) power = power * 5 / 4;
    if (command == Command::Guard) return 0;
    return boundedDamage(power, totalDefense(defender) / 5, guarding);
}

TurnResult Battle::step(Command playerCommand) {
    TurnResult result;
    result.playerCommand = playerCommand;
    result.outcome = outcome_;
    if (outcome_ != BattleOutcome::Ongoing) return result;

    if (playerCommand == Command::HeavyStrike && player_.energy < kHeavyCost)
        playerCommand = Command::Strike;
    if (playerCommand == Command::Boost && player_.energy < kBoostCost)
        playerCommand = Command::Strike;

    result.playerCommand = playerCommand;
    result.botCommand = chooseBotCommand();
    const bool playerGuarding = playerCommand == Command::Guard;
    const bool botGuarding = result.botCommand == Command::Guard;

    if (playerCommand == Command::HeavyStrike) player_.energy -= kHeavyCost;
    else if (playerCommand == Command::Boost) player_.energy -= kBoostCost;
    else player_.energy = std::min(player_.maxEnergy, player_.energy + 8);

    if (result.botCommand == Command::HeavyStrike) bot_.energy -= kHeavyCost;
    else if (result.botCommand == Command::Boost) bot_.energy -= kBoostCost;
    else bot_.energy = std::min(bot_.maxEnergy, bot_.energy + 8);

    result.botDamage = resolveDamage(botBuild_, bot_, playerBuild_, player_,
                                     result.botCommand, playerGuarding);
    result.playerDamage = resolveDamage(playerBuild_, player_, botBuild_, bot_,
                                        playerCommand, botGuarding);

    if (result.botDamage > 0) {
        auto& hp = player_.hp[weakestPart(player_)];
        hp = std::max(0, hp - result.botDamage);
    }
    if (result.playerDamage > 0) {
        auto& hp = bot_.hp[weakestPart(bot_)];
        hp = std::max(0, hp - result.playerDamage);
    }

    ++turn_;
    const int playerHp = playerTotalHp();
    const int botHp = botTotalHp();
    if (playerHp == 0 && botHp == 0) outcome_ = BattleOutcome::Draw;
    else if (botHp == 0) outcome_ = BattleOutcome::PlayerWin;
    else if (playerHp == 0) outcome_ = BattleOutcome::BotWin;

    result.outcome = outcome_;
    if (outcome_ == BattleOutcome::PlayerWin) result.coinsAwarded = kVictoryReward;
    return result;
}

int LocalProfile::coins() { return cocos2d::UserDefault::getInstance()->getIntegerForKey("rf.coins", 0); }
int LocalProfile::battles() { return cocos2d::UserDefault::getInstance()->getIntegerForKey("rf.battles", 0); }
int LocalProfile::wins() { return cocos2d::UserDefault::getInstance()->getIntegerForKey("rf.wins", 0); }
int LocalProfile::losses() { return cocos2d::UserDefault::getInstance()->getIntegerForKey("rf.losses", 0); }

int LocalProfile::unlockedStages() {
    const int saved = cocos2d::UserDefault::getInstance()->getIntegerForKey(
        "rf.campaign.unlocked", 1);
    return std::max(1, std::min(6, saved));
}

bool LocalProfile::isStageUnlocked(int stageIndex) {
    return stageIndex >= 0 && stageIndex < unlockedStages();
}

bool LocalProfile::isStageComplete(int stageIndex) {
    if (stageIndex < 0 || stageIndex >= 6) return false;
    char key[64];
    std::snprintf(key, sizeof(key), "rf.campaign.stage.%d.complete", stageIndex);
    return cocos2d::UserDefault::getInstance()->getBoolForKey(key, false);
}

void LocalProfile::recordStageVictory(int stageIndex) {
    if (stageIndex < 0 || stageIndex >= 6) return;
    auto* save = cocos2d::UserDefault::getInstance();
    char key[64];
    std::snprintf(key, sizeof(key), "rf.campaign.stage.%d.complete", stageIndex);
    save->setBoolForKey(key, true);
    const int nextUnlocked = std::min(6, std::max(unlockedStages(), stageIndex + 2));
    save->setIntegerForKey("rf.campaign.unlocked", nextUnlocked);
    save->flush();
}

void LocalProfile::recordResult(BattleOutcome outcome) {
    if (outcome == BattleOutcome::Ongoing) return;
    auto* save = cocos2d::UserDefault::getInstance();
    save->setIntegerForKey("rf.battles", battles() + 1);
    if (outcome == BattleOutcome::PlayerWin) {
        save->setIntegerForKey("rf.coins", coins() + kVictoryReward);
        save->setIntegerForKey("rf.wins", wins() + 1);
    } else if (outcome == BattleOutcome::BotWin) {
        save->setIntegerForKey("rf.losses", losses() + 1);
    }
    // Draws and ongoing battles never grant currency.
    save->flush();
}

void LocalProfile::resetForTests(int value) {
    auto* save = cocos2d::UserDefault::getInstance();
    save->setIntegerForKey("rf.coins", std::max(0, value));
    save->setIntegerForKey("rf.battles", 0);
    save->setIntegerForKey("rf.wins", 0);
    save->setIntegerForKey("rf.losses", 0);
    save->flush();
}
} // namespace robotfight
