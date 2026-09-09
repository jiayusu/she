import Foundation

let supportedContractVersion = "1.0"

protocol VersionedContract {
    var contractVersion: String { get }
}

enum MasteryState: String, Codable, CaseIterable, Sendable {
    case unseen = "UNSEEN"
    case heard = "HEARD"
    case comprehended = "COMPREHENDED"
    case imitated = "IMITATED"
    case promptedOutput = "PROMPTED_OUTPUT"
    case spontaneousOutput = "SPONTANEOUS_OUTPUT"
    case transferred = "TRANSFERRED"
}

enum EvidenceKind: String, Codable, Sendable {
    case prompted
    case spontaneous
    case transferred
    case comprehension
}

enum TeachingPressure: String, Codable, CaseIterable, Sendable {
    case low
    case normal
}

struct PetSummary: Codable, Equatable, Sendable {
    let name: String
    let mood: String
    let accessibilityLabel: String

    enum CodingKeys: String, CodingKey {
        case name, mood
        case accessibilityLabel = "accessibility_label"
    }
}

struct HighlightSummary: Codable, Equatable, Sendable {
    let text: String
    let evidenceID: String

    enum CodingKeys: String, CodingKey {
        case text
        case evidenceID = "evidence_id"
    }
}

struct TodayTask: Codable, Equatable, Sendable {
    let title: String
    let subtitle: String
    let progress: Double
    let actionLabel: String

    enum CodingKeys: String, CodingKey {
        case title, subtitle, progress
        case actionLabel = "action_label"
    }
}

struct DashboardMetrics: Codable, Equatable, Sendable {
    let spontaneousSpeakingCount: Int
    let unpromptedOutputCount: Int
    let newWords: [String]

    enum CodingKeys: String, CodingKey {
        case spontaneousSpeakingCount = "spontaneous_speaking_count"
        case unpromptedOutputCount = "unprompted_output_count"
        case newWords = "new_words"
    }
}

struct DeviceSummary: Codable, Equatable, Sendable {
    let deviceID: String
    let name: String
    let online: Bool
    let batteryPercent: Int?

    enum CodingKeys: String, CodingKey {
        case deviceID = "device_id"
        case name, online
        case batteryPercent = "battery_percent"
    }
}

struct DashboardSnapshot: Codable, Equatable, Sendable, VersionedContract {
    let contractVersion: String
    let generatedAt: String
    let greeting: String
    let pet: PetSummary
    let highlight: HighlightSummary
    let task: TodayTask
    let metrics: DashboardMetrics
    let device: DeviceSummary
    let mock: Bool

    enum CodingKeys: String, CodingKey {
        case contractVersion = "contract_version"
        case generatedAt = "generated_at"
        case greeting, pet, highlight, task, metrics, device, mock
    }
}

struct LearningEvidence: Codable, Equatable, Identifiable, Sendable {
    let evidenceID: String
    let kind: EvidenceKind
    let expression: String
    let occurredAt: String
    let confidence: Double

    var id: String { evidenceID }

    enum CodingKeys: String, CodingKey {
        case evidenceID = "evidence_id"
        case kind, expression
        case occurredAt = "occurred_at"
        case confidence
    }
}

struct MasteryUpdate: Codable, Equatable, Sendable {
    let expression: String
    let from: MasteryState
    let to: MasteryState
    let evidenceIDs: [String]

    enum CodingKeys: String, CodingKey {
        case expression, from, to
        case evidenceIDs = "evidence_ids"
    }
}

struct WeeklyReport: Codable, Equatable, Sendable, VersionedContract {
    let contractVersion: String
    let periodStart: String
    let periodEnd: String
    let spontaneousSpeakingCount: Int
    let promptedSpeakingCount: Int
    let newSpontaneousWords: [String]
    let transferredWords: [String]
    let currentFocus: String
    let scaffoldTrend: String
    let evidence: [LearningEvidence]
    let masteryUpdates: [MasteryUpdate]
    let mock: Bool

    enum CodingKeys: String, CodingKey {
        case contractVersion = "contract_version"
        case periodStart = "period_start"
        case periodEnd = "period_end"
        case spontaneousSpeakingCount = "spontaneous_speaking_count"
        case promptedSpeakingCount = "prompted_speaking_count"
        case newSpontaneousWords = "new_spontaneous_words"
        case transferredWords = "transferred_words"
        case currentFocus = "current_focus"
        case scaffoldTrend = "scaffold_trend"
        case evidence
        case masteryUpdates = "mastery_updates"
        case mock
    }
}

struct DeviceSettings: Codable, Equatable, Sendable, VersionedContract {
    let contractVersion: String
    let deviceID: String
    let name: String
    let online: Bool
    let batteryPercent: Int?
    var volume: Int
    var ledEnabled: Bool
    var cameraEnabled: Bool
    var rawAudioUploadEnabled: Bool
    let firmwareVersion: String
    let lastSeenAt: String
    let mock: Bool

    enum CodingKeys: String, CodingKey {
        case contractVersion = "contract_version"
        case deviceID = "device_id"
        case name, online
        case batteryPercent = "battery_percent"
        case volume
        case ledEnabled = "led_enabled"
        case cameraEnabled = "camera_enabled"
        case rawAudioUploadEnabled = "raw_audio_upload_enabled"
        case firmwareVersion = "firmware_version"
        case lastSeenAt = "last_seen_at"
        case mock
    }
}

struct DeviceSettingsPatch: Codable, Equatable, Sendable {
    var volume: Int?
    var ledEnabled: Bool?
    var cameraEnabled: Bool?
    var rawAudioUploadEnabled: Bool?

    init(
        volume: Int? = nil,
        ledEnabled: Bool? = nil,
        cameraEnabled: Bool? = nil,
        rawAudioUploadEnabled: Bool? = nil
    ) {
        self.volume = volume
        self.ledEnabled = ledEnabled
        self.cameraEnabled = cameraEnabled
        self.rawAudioUploadEnabled = rawAudioUploadEnabled
    }

    enum CodingKeys: String, CodingKey {
        case volume
        case ledEnabled = "led_enabled"
        case cameraEnabled = "camera_enabled"
        case rawAudioUploadEnabled = "raw_audio_upload_enabled"
    }
}

struct ParentConstraints: Codable, Equatable, Sendable, VersionedContract {
    let contractVersion: String
    var sessionBudgetSeconds: Int
    var preferredTopics: [String]
    var avoidTopics: [String]
    var nextDayContext: String
    var teachingPressure: TeachingPressure
    let updatedAt: String
    let mock: Bool

    enum CodingKeys: String, CodingKey {
        case contractVersion = "contract_version"
        case sessionBudgetSeconds = "session_budget_seconds"
        case preferredTopics = "preferred_topics"
        case avoidTopics = "avoid_topics"
        case nextDayContext = "next_day_context"
        case teachingPressure = "teaching_pressure"
        case updatedAt = "updated_at"
        case mock
    }
}

struct ParentConstraintsUpdate: Codable, Equatable, Sendable {
    let sessionBudgetSeconds: Int
    let preferredTopics: [String]
    let avoidTopics: [String]
    let nextDayContext: String
    let teachingPressure: TeachingPressure

    enum CodingKeys: String, CodingKey {
        case sessionBudgetSeconds = "session_budget_seconds"
        case preferredTopics = "preferred_topics"
        case avoidTopics = "avoid_topics"
        case nextDayContext = "next_day_context"
        case teachingPressure = "teaching_pressure"
    }
}

struct PrivacyOperation: Codable, Equatable, Sendable, VersionedContract {
    let contractVersion: String
    let operation: String
    let status: String
    let mock: Bool
    let storeMutated: Bool

    enum CodingKeys: String, CodingKey {
        case contractVersion = "contract_version"
        case operation, status, mock
        case storeMutated = "store_mutated"
    }
}

struct RpgReadIdentity: Equatable, Sendable {
    let childID: String
    let sessionID: String

    init?(childID: String?, sessionID: String?) {
        guard
            let childID,
            let sessionID,
            Self.isGatewayIdentity(childID),
            Self.isGatewayIdentity(sessionID)
        else { return nil }
        self.childID = childID
        self.sessionID = sessionID
    }

    private static func isGatewayIdentity(_ value: String) -> Bool {
        value.range(
            of: "^[A-Za-z0-9_-]{1,80}$",
            options: .regularExpression
        ) != nil
    }
}

private struct AnyContractCodingKey: CodingKey {
    let stringValue: String
    let intValue: Int?

    init?(stringValue: String) {
        self.stringValue = stringValue
        self.intValue = nil
    }

    init?(intValue: Int) {
        self.stringValue = String(intValue)
        self.intValue = intValue
    }
}

private func rejectUnknownKeys<Key>(
    _ decoder: Decoder,
    allowedBy _: Key.Type
) throws where Key: CodingKey & CaseIterable {
    let raw = try decoder.container(keyedBy: AnyContractCodingKey.self)
    let allowed = Set(Key.allCases.map(\.stringValue))
    if let unknown = raw.allKeys.first(where: { !allowed.contains($0.stringValue) }) {
        throw DecodingError.dataCorruptedError(
            forKey: unknown,
            in: raw,
            debugDescription: "Unexpected contract field: \(unknown.stringValue)"
        )
    }
}

enum RpgDeliveryStatus: String, Decodable, Equatable, Sendable {
    case planned
    case issuing
    case completed
    case failed
    case expired
}

enum RpgNodeID: String, Decodable, Equatable, Sendable {
    case collectMilk = "collect_milk"
    case findRedCup = "find_red_cup"
    case picnicReady = "picnic_ready"
}

enum RpgQuestPhase: String, Decodable, Equatable, Sendable {
    case seekingObject = "seeking_object"
    case confirmingObject = "confirming_object"
    case presenting
    case awaitingSpeech = "awaiting_speech"
    case resolving
    case paused
    case deliveryFailed = "delivery_failed"
    case completed
}

enum RpgObjectID: String, Decodable, Equatable, Sendable {
    case fridge
    case table
    case redCup = "red_cup"
    case blueCup = "blue_cup"
}

enum RpgInventoryItem: String, Decodable, Equatable, Sendable {
    case milkToken = "milk_token"
    case redCupToken = "red_cup_token"
}

enum RpgWorldRole: String, Decodable, Equatable, Sendable {
    case drinkKeeper = "饮品保管员"
    case cupKeeper = "杯子管理员"
    case picnicGuide = "野餐向导"
}

enum RpgActionKind: String, Decodable, Equatable, Sendable {
    case ask
    case reinvite
    case prompt
    case recast
    case advanceStory = "advance_story"
    case explore
    case pause
}

struct RpgQuest: Decodable, Equatable, Sendable {
    let seedID: String
    let seedVersion: Int
    let nodeID: RpgNodeID
    let phase: RpgQuestPhase
    let worldRevision: Int
    let inventory: [RpgInventoryItem]
    let completedNodes: [RpgNodeID]
    let confirmedObject: RpgObjectID?
    let worldRole: RpgWorldRole
    let actionKind: RpgActionKind
    let targetExpression: String
    let promptID: String?
    let feedbackID: String
    let nextQuestID: RpgNodeID?

    enum CodingKeys: String, CodingKey, CaseIterable {
        case seedID = "seed_id"
        case seedVersion = "seed_version"
        case nodeID = "node_id"
        case phase
        case worldRevision = "world_revision"
        case inventory
        case completedNodes = "completed_nodes"
        case confirmedObject = "confirmed_object"
        case worldRole = "world_role"
        case actionKind = "action_kind"
        case targetExpression = "target_expression"
        case promptID = "prompt_id"
        case feedbackID = "feedback_id"
        case nextQuestID = "next_quest_id"
    }

    init(
        seedID: String,
        seedVersion: Int,
        nodeID: RpgNodeID,
        phase: RpgQuestPhase,
        worldRevision: Int,
        inventory: [RpgInventoryItem],
        completedNodes: [RpgNodeID],
        confirmedObject: RpgObjectID?,
        worldRole: RpgWorldRole,
        actionKind: RpgActionKind,
        targetExpression: String,
        promptID: String?,
        feedbackID: String,
        nextQuestID: RpgNodeID?
    ) {
        self.seedID = seedID
        self.seedVersion = seedVersion
        self.nodeID = nodeID
        self.phase = phase
        self.worldRevision = worldRevision
        self.inventory = inventory
        self.completedNodes = completedNodes
        self.confirmedObject = confirmedObject
        self.worldRole = worldRole
        self.actionKind = actionKind
        self.targetExpression = targetExpression
        self.promptID = promptID
        self.feedbackID = feedbackID
        self.nextQuestID = nextQuestID
    }

    init(from decoder: Decoder) throws {
        try rejectUnknownKeys(decoder, allowedBy: CodingKeys.self)
        let container = try decoder.container(keyedBy: CodingKeys.self)
        seedID = try container.decode(String.self, forKey: .seedID)
        seedVersion = try container.decode(Int.self, forKey: .seedVersion)
        nodeID = try container.decode(RpgNodeID.self, forKey: .nodeID)
        phase = try container.decode(RpgQuestPhase.self, forKey: .phase)
        worldRevision = try container.decode(Int.self, forKey: .worldRevision)
        inventory = try container.decode([RpgInventoryItem].self, forKey: .inventory)
        completedNodes = try container.decode([RpgNodeID].self, forKey: .completedNodes)
        guard container.contains(.confirmedObject) else {
            throw DecodingError.keyNotFound(
                CodingKeys.confirmedObject,
                .init(codingPath: decoder.codingPath, debugDescription: "Missing confirmed_object")
            )
        }
        confirmedObject = try container.decodeIfPresent(RpgObjectID.self, forKey: .confirmedObject)
        worldRole = try container.decode(RpgWorldRole.self, forKey: .worldRole)
        actionKind = try container.decode(RpgActionKind.self, forKey: .actionKind)
        targetExpression = try container.decode(String.self, forKey: .targetExpression)
        guard container.contains(.promptID) else {
            throw DecodingError.keyNotFound(
                CodingKeys.promptID,
                .init(codingPath: decoder.codingPath, debugDescription: "Missing prompt_id")
            )
        }
        promptID = try container.decodeIfPresent(String.self, forKey: .promptID)
        feedbackID = try container.decode(String.self, forKey: .feedbackID)
        guard container.contains(.nextQuestID) else {
            throw DecodingError.keyNotFound(
                CodingKeys.nextQuestID,
                .init(codingPath: decoder.codingPath, debugDescription: "Missing next_quest_id")
            )
        }
        nextQuestID = try container.decodeIfPresent(RpgNodeID.self, forKey: .nextQuestID)
        guard isCanonicalMilkPicnicState else {
            throw DecodingError.dataCorrupted(
                .init(codingPath: decoder.codingPath, debugDescription: "Invalid milk_picnic.v1 state")
            )
        }
    }

    var isCanonicalMilkPicnicState: Bool {
        guard seedID == "milk_picnic", seedVersion == 1, worldRevision >= 0 else {
            return false
        }
        switch phase {
        case .presenting, .awaitingSpeech, .resolving, .deliveryFailed:
            guard confirmedObject != nil else { return false }
        case .seekingObject, .confirmingObject, .completed:
            guard confirmedObject == nil else { return false }
        case .paused:
            break
        }

        switch nodeID {
        case .collectMilk:
            return phase != .completed
                && worldRevision == 1
                && inventory.isEmpty
                && completedNodes.isEmpty
                && (confirmedObject == nil || confirmedObject == .fridge)
                && worldRole == .drinkKeeper
                && targetExpression == "I want milk."
                && promptID.map { Self.promptIDs.contains($0) } != false
                && Self.collectMilkContentIDs.contains(feedbackID)
                && nextQuestID == .collectMilk
        case .findRedCup:
            return phase != .completed
                && worldRevision == 2
                && inventory == [.milkToken]
                && completedNodes == [.collectMilk]
                && confirmedObject.map { Self.cupObjects.contains($0) } != false
                && worldRole == .cupKeeper
                && targetExpression == "I choose the red cup."
                && promptID.map { Self.promptIDs.contains($0) } != false
                && Self.findRedCupContentIDs.contains(feedbackID)
                && nextQuestID == .findRedCup
        case .picnicReady:
            return phase == .completed
                && worldRevision == 4
                && inventory == [.milkToken, .redCupToken]
                && completedNodes == [.collectMilk, .findRedCup, .picnicReady]
                && confirmedObject == nil
                && worldRole == .picnicGuide
                && targetExpression == "Our picnic is ready."
                && promptID.map { Self.promptIDs.contains($0) } != false
                && Self.picnicReadyContentIDs.contains(feedbackID)
                && nextQuestID == nil
        }
    }

    private static let cupObjects: Set<RpgObjectID> = [.table, .redCup, .blueCup]
    private static let promptIDs: Set<String> = Set(
        ["collect_milk", "find_red_cup", "picnic_ready"].flatMap { node in
            (0...6).map { "\(node)_s\($0)" }
        }
    )
    private static let collectMilkContentIDs: Set<String> = Set((0...6).map { "collect_milk_s\($0)" })
        .union(["milk_help"])
    private static let findRedCupContentIDs: Set<String> = Set((0...6).map { "find_red_cup_s\($0)" })
        .union(["milk_ready", "red_cup_help"])
    private static let picnicReadyContentIDs: Set<String> = Set((0...6).map { "picnic_ready_s\($0)" })
        .union(["red_cup_ready", "picnic_complete", "picnic_pause"])
}

struct RpgQuestSummary: Decodable, Equatable, Sendable, VersionedContract {
    let contractVersion: String
    let learningRevision: Int
    let turnID: String?
    let deliveryStatus: RpgDeliveryStatus?
    let quest: RpgQuest?

    enum CodingKeys: String, CodingKey, CaseIterable {
        case contractVersion = "contract_version"
        case learningRevision = "learning_revision"
        case turnID = "turn_id"
        case deliveryStatus = "delivery_status"
        case quest
    }

    init(
        contractVersion: String,
        learningRevision: Int,
        turnID: String?,
        deliveryStatus: RpgDeliveryStatus?,
        quest: RpgQuest?
    ) {
        self.contractVersion = contractVersion
        self.learningRevision = learningRevision
        self.turnID = turnID
        self.deliveryStatus = deliveryStatus
        self.quest = quest
    }

    init(from decoder: Decoder) throws {
        try rejectUnknownKeys(decoder, allowedBy: CodingKeys.self)
        let container = try decoder.container(keyedBy: CodingKeys.self)
        contractVersion = try container.decode(String.self, forKey: .contractVersion)
        learningRevision = try container.decode(Int.self, forKey: .learningRevision)
        guard container.contains(.turnID) else {
            throw DecodingError.keyNotFound(
                CodingKeys.turnID,
                .init(codingPath: decoder.codingPath, debugDescription: "Missing turn_id")
            )
        }
        turnID = try container.decodeIfPresent(String.self, forKey: .turnID)
        guard container.contains(.deliveryStatus) else {
            throw DecodingError.keyNotFound(
                CodingKeys.deliveryStatus,
                .init(codingPath: decoder.codingPath, debugDescription: "Missing delivery_status")
            )
        }
        deliveryStatus = try container.decodeIfPresent(
            RpgDeliveryStatus.self,
            forKey: .deliveryStatus
        )
        guard container.contains(.quest) else {
            throw DecodingError.keyNotFound(
                CodingKeys.quest,
                .init(codingPath: decoder.codingPath, debugDescription: "Missing quest")
            )
        }
        quest = try container.decodeIfPresent(RpgQuest.self, forKey: .quest)
    }

    var isCanonicalProjection: Bool {
        guard contractVersion == supportedContractVersion, learningRevision >= 0 else {
            return false
        }
        if let turnID {
            guard turnID.range(
                of: "^[A-Za-z0-9_.-]{1,120}$",
                options: .regularExpression
            ) != nil else { return false }
        }
        return quest?.isCanonicalMilkPicnicState != false
    }
}
