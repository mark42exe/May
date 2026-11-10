#include "HelloWorldScene.h"

#include <algorithm>
#include <cctype>
#include <sstream>
#include <string>
#include <vector>

USING_NS_CC;

namespace {
struct SceneInspection {
    bool loaded = false;
    bool rccb = false;
    std::size_t bytes = 0;
    std::size_t printableStrings = 0;
    std::size_t resourceRefs = 0;
    std::string summary;
};

SceneInspection inspectOriginalBattleScene() {
    SceneInspection out;
    Data data = FileUtils::getInstance()->getDataFromFile("RFBattleLayer.ccb");
    if (data.isNull() || data.getSize() < 16) {
        out.summary = "RFBattleLayer.ccb not found in app Resources";
        return out;
    }

    out.loaded = true;
    out.bytes = data.getSize();
    const unsigned char* bytes = data.getBytes();
    out.rccb = bytes[4] == 'R' && bytes[5] == 'C' &&
               bytes[6] == 'C' && bytes[7] == 'B';

    std::vector<std::string> strings;
    std::size_t i = 0;
    while (i < out.bytes) {
        while (i < out.bytes && (bytes[i] < 0x20 || bytes[i] > 0x7e)) ++i;
        const std::size_t begin = i;
        while (i < out.bytes && bytes[i] >= 0x20 && bytes[i] <= 0x7e) ++i;
        if (i - begin >= 4) {
            strings.emplace_back(reinterpret_cast<const char*>(bytes + begin), i - begin);
        }
    }
    out.printableStrings = strings.size();

    const char* extensions[] = {".webp", ".png", ".jpg", ".jpeg", ".ttf", ".fnt", ".plist", ".json"};
    for (const auto& value : strings) {
        for (const char* ext : extensions) {
            const std::size_t n = std::char_traits<char>::length(ext);
            if (value.size() >= n && value.compare(value.size() - n, n, ext) == 0) {
                ++out.resourceRefs;
                break;
            }
        }
    }

    std::ostringstream text;
    text << "Original battle scene loaded\n"
         << "Signature: " << (out.rccb ? "RCCB" : "unknown") << "\n"
         << "Binary size: " << out.bytes << " bytes\n"
         << "Printable records: " << out.printableStrings << "\n"
         << "Resource references: " << out.resourceRefs << "\n\n"
         << "This is a native Cocos2d-x ARM64 scene-loader test.\n"
         << "The proprietary RCCB object hierarchy is not decoded yet.";
    out.summary = text.str();
    return out;
}
}

Scene* HelloWorld::createScene() {
    return HelloWorld::create();
}

bool HelloWorld::init() {
    if (!Scene::init()) return false;

    const auto size = Director::getInstance()->getVisibleSize();
    const auto origin = Director::getInstance()->getVisibleOrigin();

    auto background = DrawNode::create();
    background->drawSolidRect(Vec2::ZERO, Vec2(size.width, size.height),
                              Color4F(0.025f, 0.04f, 0.075f, 1.0f));
    addChild(background, -1);

    auto heading = Label::createWithSystemFont("ROBOT FIGHT / NATIVE PORT", "Arial", 34);
    heading->setTextColor(Color4B(230, 240, 255, 255));
    heading->setAnchorPoint(Vec2(0.5f, 1.0f));
    heading->setPosition(Vec2(origin.x + size.width * 0.5f, origin.y + size.height - 42));
    addChild(heading);

    const auto inspection = inspectOriginalBattleScene();
    auto detail = Label::createWithSystemFont(inspection.summary, "Arial", 21);
    detail->setTextColor(Color4B(160, 190, 220, 255));
    detail->setAlignment(TextHAlignment::CENTER, TextVAlignment::CENTER);
    detail->setDimensions(size.width * 0.86f, size.height * 0.62f);
    detail->setPosition(Vec2(origin.x + size.width * 0.5f, origin.y + size.height * 0.48f));
    addChild(detail);

    auto footer = Label::createWithSystemFont(
        "Offline ARM64 runtime validation  |  Original scene data",
        "Arial", 16);
    footer->setTextColor(Color4B(100, 130, 165, 255));
    footer->setPosition(Vec2(origin.x + size.width * 0.5f, origin.y + 28));
    addChild(footer);

    return true;
}
