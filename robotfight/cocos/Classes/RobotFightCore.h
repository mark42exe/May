#pragma once

#include <array>
#include <cstdint>
#include <string>

namespace robotfight {

enum class PartSlot : std::uint8_t { Base, Core, Head, FrontArm, BackArm, Count };
enum class BattleOutcome : std::uint8_t { Ongoing, PlayerWin, BotWin, Draw };
enum class Command : std::uint8_t { Guard, Strike, HeavyStrike, Boost };

struct PartStats {
    int health;
    int attack;
    int defense;
    int energy;
};

struct RobotBuild {
    std::string id;
    std::string displayName;
    std::array<PartStats, static_cast<std::size_t>(PartSlot::Count)> parts;
};

struct RobotState {
    std::array<int, static_cast<std::size_t>(PartSlot::Count)> hp{};
    int energy = 100;
    int wins = 0;
    int losses = 0;
};

struct TurnResult {
    Command playerCommand = Command::Guard;
    Command botCommand = Command::Guard;
    int playerDamage = 0;
    int botDamage = 0;
    BattleOutcome outcome = BattleOutcome::Ongoing;
    int coinsAwarded = 0;
};

class Battle {
public:
    Battle(const RobotBuild& player, const RobotBuild& bot, std::uint32_t seed);
    TurnResult step(Command playerCommand);
    const RobotState& playerState() const { return player_; }
    const RobotState& botState() const { return bot_; }
    BattleOutcome outcome() const { return outcome_; }
    int playerTotalHp() const;
    int botTotalHp() const;

private:
    Command chooseBotCommand();
    int resolveDamage(const RobotBuild& attacker, const RobotState& attackerState,
                      const RobotBuild& defender, const RobotState& defenderState,
                      Command command, bool guarding) const;
    static std::size_t weakestPart(const RobotState& state);

    RobotBuild playerBuild_;
    RobotBuild botBuild_;
    RobotState player_;
    RobotState bot_;
    BattleOutcome outcome_ = BattleOutcome::Ongoing;
    std::uint32_t rng_;
    unsigned turn_ = 0;
};

class LocalProfile {
public:
    static int coins();
    static int wins();
    static int losses();
    static void recordResult(BattleOutcome outcome);
    static void resetForTests(int coins = 0);
};

} // namespace robotfight
