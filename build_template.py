import json

template = {
    "template_name": "Murim/Magic",
    "description": "A world where ancient Murim cultivation meets arcane magic — the Merged Realms, born from a cataclysm that shattered two worlds together.",
    "locations": [
        {"name": "Mount Tianlun — The Jade Palace", "description": "The sacred peak of the Murim Alliance, a fortress-monastery carved into the mountain face. Training grounds, council chambers, and the Azure Cloud Sect's former home.", "short_description": "Headquarters of the Murim Alliance", "location_type": "city", "is_safe": True, "is_indoors": False, "biome": "mountain", "danger_level": 1, "population_density": "dense", "map_x": 50, "map_y": 30, "resources": {"Spirit Herbs": {"dc": 14, "max_qty": 3}, "Qi Crystals": {"dc": 18, "max_qty": 1}, "Mountain Stone": {"dc": 10, "max_qty": 5}}, "connections": [{"direction": "south", "target_name": "The Convergence Market"}, {"direction": "east", "target_name": "The Spire of Convergence"}]},
        {"name": "The Spire of Convergence", "description": "A hybrid tower of impossible architecture — half-Murim pagoda, half-arcane spire — floating above Mount Tianlun. The Arcane Council headquarters.", "short_description": "Arcane Council Headquarters", "location_type": "city", "is_safe": True, "is_indoors": True, "biome": "mountain", "danger_level": 2, "population_density": "dense", "map_x": 55, "map_y": 25, "resources": {"Arcane Residue": {"dc": 15, "max_qty": 2}, "Mana Crystal": {"dc": 20, "max_qty": 1}}, "connections": [{"direction": "west", "target_name": "Mount Tianlun — The Jade Palace"}, {"direction": "down", "target_name": "The Convergence Market"}]},
        {"name": "The Convergence Market", "description": "Sprawling city-sized bazaar at the base of Mount Tianlun. Anything can be bought or sold here.", "short_description": "The economic heart of the Merged Realms", "location_type": "city", "is_safe": True, "is_indoors": False, "biome": "plains", "danger_level": 2, "population_density": "dense", "map_x": 50, "map_y": 40, "resources": {"Gathered Intelligence": {"dc": 12, "max_qty": 1}, "Exotic Spice": {"dc": 10, "max_qty": 4}}, "connections": [{"direction": "north", "target_name": "Mount Tianlun — The Jade Palace"}, {"direction": "south", "target_name": "The Southern Kingdoms"}, {"direction": "west", "target_name": "The Crimson Desert"}]},
        {"name": "The Black Mountains — Abyss Palace", "description": "The corrupted fortress of the Heavenly Demon Cult, built into the caldera of an active volcano.", "short_description": "Headquarters of the Heavenly Demon Cult", "location_type": "dungeon", "is_safe": False, "is_indoors": True, "biome": "mountain", "danger_level": 5, "population_density": "sparse", "map_x": 80, "map_y": 20, "resources": {"Demonic Qi Fragment": {"dc": 20, "max_qty": 1}, "Volcanic Ore": {"dc": 16, "max_qty": 2}}, "connections": [{"direction": "south", "target_name": "The Verdant Wound"}, {"direction": "east", "target_name": "The Whispering Wastes"}]},
        {"name": "The Southern Kingdoms", "description": "Three mortal kingdoms — Yan, Wei, and Zhao — united under the Tri-Kingdom Compact.", "short_description": "The last mortal kingdoms", "location_type": "city", "is_safe": True, "is_indoors": False, "biome": "plains", "danger_level": 2, "population_density": "dense", "map_x": 50, "map_y": 70, "resources": {"Common Herbs": {"dc": 8, "max_qty": 5}, "Iron Ore": {"dc": 12, "max_qty": 3}}, "connections": [{"direction": "north", "target_name": "The Convergence Market"}, {"direction": "west", "target_name": "The Serpent River"}]},
        {"name": "The Serpent River", "description": "The heavily fortified front line between Alliance and Cult territories.", "short_description": "The war front", "location_type": "wilderness", "is_safe": False, "is_indoors": False, "biome": "plains", "danger_level": 4, "population_density": "moderate", "map_x": 35, "map_y": 60, "resources": {"War Salvage": {"dc": 14, "max_qty": 2}, "River Reed": {"dc": 10, "max_qty": 4}, "Corrupted Qi Shard": {"dc": 18, "max_qty": 1}}, "connections": [{"direction": "north", "target_name": "The Whispering Wastes"}, {"direction": "east", "target_name": "The Southern Kingdoms"}, {"direction": "west", "target_name": "The Verdant Wound"}]},
        {"name": "The Verdant Wound", "description": "The largest open rift — a miles-long tear in reality hanging in the sky.", "short_description": "The largest rift zone", "location_type": "dungeon", "is_safe": False, "is_indoors": False, "biome": "plains", "danger_level": 5, "population_density": "sparse", "map_x": 30, "map_y": 40, "resources": {"Rift Energy Crystal": {"dc": 18, "max_qty": 1}, "Convergence Fragment": {"dc": 22, "max_qty": 1}, "Void Stone": {"dc": 20, "max_qty": 1}}, "connections": [{"direction": "north", "target_name": "The Black Mountains — Abyss Palace"}, {"direction": "east", "target_name": "The Serpent River"}]},
        {"name": "The Silverwood Forest", "description": "A vast forest of silver-barked trees glowing with bioluminescent magic, slowly dying from the Withering.", "short_description": "The elven forest refuge", "location_type": "forest", "is_safe": True, "is_indoors": False, "biome": "forest", "danger_level": 2, "population_density": "sparse", "map_x": 20, "map_y": 30, "resources": {"Moonbloom": {"dc": 12, "max_qty": 4}, "Silver Bark": {"dc": 15, "max_qty": 2}, "Withered Heartwood": {"dc": 18, "max_qty": 1}}, "connections": [{"direction": "south", "target_name": "The Floating Isles of Aerendor"}, {"direction": "east", "target_name": "The Convergence Market"}]},
        {"name": "The Floating Isles of Aerendor", "description": "Seven sky-islands drifting above the Crimson Desert, home to mages and scholars.", "short_description": "Sky-islands of mages", "location_type": "city", "is_safe": True, "is_indoors": True, "biome": "mountain", "danger_level": 1, "population_density": "moderate", "map_x": 20, "map_y": 50, "resources": {"Sky Crystal": {"dc": 16, "max_qty": 2}, "Arcane Codex Page": {"dc": 20, "max_qty": 1}}, "connections": [{"direction": "north", "target_name": "The Silverwood Forest"}, {"direction": "down", "target_name": "The Crimson Desert"}]},
        {"name": "The Crimson Desert", "description": "Red sand desert with Dominion ruins being uncovered by shifting sands.", "short_description": "Red sand desert with ruins", "location_type": "wilderness", "is_safe": False, "is_indoors": False, "biome": "desert", "danger_level": 3, "population_density": "sparse", "map_x": 30, "map_y": 55, "resources": {"Blood Sand": {"dc": 12, "max_qty": 5}, "Dominion Artifact Shard": {"dc": 18, "max_qty": 1}, "Desert Cactus Bloom": {"dc": 14, "max_qty": 3}}, "connections": [{"direction": "north", "target_name": "The Convergence Market"}, {"direction": "east", "target_name": "The Southern Kingdoms"}, {"direction": "up", "target_name": "The Floating Isles of Aerendor"}]},
        {"name": "The Whispering Wastes", "description": "A desolate wasteland where sands whisper secrets. Home to necromancers and exiles.", "short_description": "Haunted wasteland", "location_type": "wilderness", "is_safe": False, "is_indoors": False, "biome": "desert", "danger_level": 4, "population_density": "sparse", "map_x": 70, "map_y": 30, "resources": {"Soul Residue": {"dc": 16, "max_qty": 2}, "Bone Dust": {"dc": 12, "max_qty": 4}, "Pale Hand Sigil": {"dc": 22, "max_qty": 1}}, "connections": [{"direction": "south", "target_name": "The Serpent River"}, {"direction": "west", "target_name": "The Black Mountains — Abyss Palace"}]},
        {"name": "The Dragon's Teeth Mountains", "description": "A volcanic mountain range ruled by the Ebon Scale Covenant.", "short_description": "Dragon territory", "location_type": "mountain", "is_safe": False, "is_indoors": False, "biome": "mountain", "danger_level": 5, "population_density": "sparse", "map_x": 80, "map_y": 60, "resources": {"Dragon Scale Fragment": {"dc": 22, "max_qty": 1}, "Volcanic Ore": {"dc": 14, "max_qty": 3}, "Ember Crystal": {"dc": 18, "max_qty": 2}}, "connections": [{"direction": "north", "target_name": "The Isle of Whispers"}, {"direction": "west", "target_name": "The Southern Kingdoms"}]},
        {"name": "The Bridge of Sighs", "description": "A massive thirty-mile stone bridge connecting to the Isle of Whispers.", "short_description": "The bridge to forgotten lands", "location_type": "wilderness", "is_safe": True, "is_indoors": False, "biome": "coastal", "danger_level": 2, "population_density": "moderate", "map_x": 85, "map_y": 75, "resources": {"Coastal Salt Crystal": {"dc": 10, "max_qty": 5}, "Old Bridge Stone": {"dc": 8, "max_qty": 6}}, "connections": [{"direction": "east", "target_name": "The Isle of Whispers"}, {"direction": "west", "target_name": "The Dragon's Teeth Mountains"}]},
        {"name": "The Isle of Whispers", "description": "The largest surviving fragment of the Arcane Dominion with First Age ruins.", "short_description": "Uncharted Dominion island", "location_type": "wilderness", "is_safe": False, "is_indoors": False, "biome": "forest", "danger_level": 4, "population_density": "sparse", "map_x": 90, "map_y": 80, "resources": {"Dominion Artifact": {"dc": 18, "max_qty": 1}, "First Age Scroll": {"dc": 22, "max_qty": 1}, "Ancient Runestone": {"dc": 20, "max_qty": 1}}, "connections": [{"direction": "west", "target_name": "The Bridge of Sighs"}]},
        {"name": "The Heartwood Nexus", "description": "The only known location where qi and mana have achieved permanent stable harmony.", "short_description": "The stable convergence point", "location_type": "shrine", "is_safe": True, "is_indoors": False, "biome": "forest", "danger_level": 1, "population_density": "sparse", "map_x": 18, "map_y": 28, "resources": {"Pure Harmonic Essence": {"dc": 20, "max_qty": 1}, "Nexus Bloom": {"dc": 16, "max_qty": 2}}, "connections": [{"direction": "surrounding", "target_name": "The Silverwood Forest"}]},
        {"name": "Necropolis Omega", "description": "The hidden capital of the Pale Hand — a city of the dead beneath the Whispering Wastes.", "short_description": "The necromancer city", "location_type": "dungeon", "is_safe": False, "is_indoors": True, "biome": "underground", "danger_level": 5, "population_density": "sparse", "map_x": 72, "map_y": 32, "resources": {"Soul Crystal": {"dc": 20, "max_qty": 1}, "Death Essence": {"dc": 18, "max_qty": 2}, "Necrotic Bone": {"dc": 14, "max_qty": 3}}, "connections": [{"direction": "up", "target_name": "The Whispering Wastes"}]}
    ],
    "guild_config": {
        "world_name": "The Merged Realms",
        "world_data": {
            "era": "Post-Merge Age",
            "calendar": "Merged Realms Standard",
            "currency": "Spirit Stones",
            "magic_type": "Qi and Mana Convergence",
            "lore": "A world born from the Rending — a cataclysm that shattered two parallel dimensions into one. Murim cultivators and arcane mages now coexist in an uneasy peace while dark forces exploit the chaos."
        }
    },
    "npcs": [
        {
            "name": "Song Linfeng", "title": "Grand Elder of the Murim Alliance", "race": "Human",
            "description": "A weathered but dignified man with silver hair. The pragmatic leader who holds the Alliance together through diplomacy, willpower, and decades of political experience.",
            "appearance": "White robes with gold embroidery, tired but sharp eyes that miss nothing.",
            "location_name": "Mount Tianlun — The Jade Palace", "disposition": "friendly",
            "greeting": "Welcome to the Jade Palace. I pray you bring good news — we have little enough of it these days.",
            "dialogue_topics": {"alliance": "The Alliance is all that stands between order and chaos — never forget that.", "war": "The Cult presses us from the west. The rifts open from below. We fight on two fronts with half the forces we need.", "cultivation": "The path is long. Do not seek the summit before you have climbed the first peak.", "merge": "When the Rending happened, we lost everything we knew. What we built since is all we have."},
            "image_url": "", "faction_name": "Murim Alliance", "proxy_mode": "automatic",
            "hp_max": 120, "armor_class": 16, "attack_bonus": 8, "damage_dice": "3d6", "damage_bonus": 4, "xp_value": 0, "gold": 500,
            "shop_inventory": {}
        },
        {
            "name": "Xuan Mo", "title": "The Crimson Demon Lord", "race": "Human (Corrupted)",
            "description": "Tall, gaunt, with pale skin and crimson eyes that burn with a cold inner light. The ruthless leader of the Heavenly Demon Cult who has consumed the inner demons of a hundred cultivators to fuel his ascension.",
            "appearance": "Black-and-crimson robes embroidered with writhing souls. His presence warps the air around him.",
            "location_name": "The Black Mountains — Abyss Palace", "disposition": "hostile",
            "greeting": "You have come to die — or to serve. There are no other options in my domain.",
            "dialogue_topics": {"power": "Power is the only law. Everything else is the lie weak people tell each other to sleep at night.", "ascension": "I will consume the Convergence Zones and become a god. The only question is whether you will be ash or servant.", "cult": "The Heavenly Demon Cult is not an organization. It is a philosophy made flesh.", "merge": "The Rending was not a disaster. It was an opportunity that only I have truly understood."},
            "image_url": "", "faction_name": "Heavenly Demon Cult", "proxy_mode": "automatic",
            "hp_max": 250, "armor_class": 20, "attack_bonus": 13, "damage_dice": "3d10", "damage_bonus": 8, "xp_value": 5000, "gold": 1000,
            "is_hostile": True, "shop_inventory": {}
        },
        {
            "name": "Seraphina Vex", "title": "Grand Archmage of the Arcane Council", "race": "Human",
            "description": "A tall, slender woman with silver-white hair and piercing blue eyes that seem to see through walls. The most politically powerful mage alive, ruling the Arcane Council with cold pragmatism.",
            "appearance": "Deep blue and silver robes covered in invisible runes, crystalline staff that hums faintly.",
            "location_name": "The Spire of Convergence", "disposition": "neutral",
            "greeting": "Welcome to the Spire. State your business clearly — my time is not to be wasted.",
            "dialogue_topics": {"merge": "The Merge was no accident. Someone or something engineered the Rending. I intend to find out who.", "magic": "Magic must be studied, understood, and regulated. Untrained mages are more dangerous than any beast.", "qi": "Qi and mana are two frequencies of the same underlying force. The first mage-cultivator hybrid will change everything.", "council": "The Arcane Council is not a democracy. It is a meritocracy. Prove your worth or go home."},
            "image_url": "", "faction_name": "Arcane Council", "proxy_mode": "automatic",
            "hp_max": 90, "armor_class": 14, "attack_bonus": 9, "damage_dice": "4d6", "damage_bonus": 3, "xp_value": 0, "gold": 300,
            "shop_inventory": {"potion": 5, "potion_great": 2}
        },
        {
            "name": "Queen Alyndra Moonshadow", "title": "Sovereign of the Silverwood", "race": "High Elf",
            "description": "An ethereally beautiful high elf with silver hair and luminous green eyes. Carries the weight of a dying civilization with quiet dignity and ancient sorrow.",
            "appearance": "Crown of living branches that bloom or wither with her mood. Robes woven from moonlight that shift color like water.",
            "location_name": "The Heartwood Nexus", "disposition": "friendly",
            "greeting": "The Silverwood welcomes you, traveler. Few mortals find this place — fewer still are permitted to stay.",
            "dialogue_topics": {"withering": "The Withering consumes my home. Each season another grove goes dark. I watch my people diminish and cannot stop it.", "elves": "My people are all that remains of a lost world. When the Rending happened, our entire civilization simply... ceased to be. We are the survivors.", "nexus": "The Heartwood Nexus is sacred — the only place qi and mana exist in perfect harmony. It cannot be allowed to fall.", "humans": "Humans are remarkable creatures. So brief, so desperate, so astonishingly tenacious."},
            "image_url": "", "faction_name": "Silverwood Dominion", "proxy_mode": "automatic",
            "hp_max": 100, "armor_class": 17, "attack_bonus": 8, "damage_dice": "2d8", "damage_bonus": 4, "xp_value": 0, "gold": 200,
            "shop_inventory": {}
        },
        {
            "name": "Deng Jie", "title": "Founder of the Rift Wardens", "race": "Human",
            "description": "A stocky, scarred man with a shaved head and a face that looks like it has been punched by every species in the Merged Realms at least once. Friendly in the way that only someone very dangerous can be.",
            "appearance": "Worn leather armor with Rift Warden insignia, a battered steel sword, and eyes that evaluate every room for exits.",
            "location_name": "The Convergence Market", "disposition": "friendly",
            "greeting": "Need a job? The Wardens always have contracts. Pull up a chair — first round's on the guild.",
            "dialogue_topics": {"wardens": "We clear rifts, hunt monsters, and get paid. No politics, no sides — just clean honest work.", "danger": "The Verdant Wound gets worse every day. Whatever's on the other side wants through, badly.", "jobs": "Current contracts: three open rifts in the Crimson Desert, an Alpha magi-beast near the Wound, and someone's monster problem in the Serpent River territory.", "fighting": "Don't be a hero. Be smart. Know when to run."},
            "image_url": "", "faction_name": "Rift Wardens", "proxy_mode": "automatic",
            "hp_max": 80, "armor_class": 15, "attack_bonus": 7, "damage_dice": "1d10", "damage_bonus": 5, "xp_value": 0, "gold": 250,
            "shop_inventory": {"longsword": 3, "shortsword": 5, "handaxe": 8, "leather": 4, "chain": 2, "potion": 10}
        },
        {
            "name": "Valthorax", "title": "The Ember King", "race": "Red Dragon",
            "description": "A massive red dragon, scales gleaming like polished rubies. In his human form, he presents as a tall, imperious man with ruby-red eyes and an air of absolute authority. The oldest living creature in the Merged Realms.",
            "appearance": "Human form: fitted red-and-black robes, ruby rings on every finger. True form: a dragon so large his wingbeats create windstorms.",
            "location_name": "The Dragon's Teeth Mountains", "disposition": "neutral",
            "greeting": "A mortal who dares approach my lair. Either you are very brave, very foolish, or you have something interesting to say. Which is it?",
            "dialogue_topics": {"merge": "The Merge is the most interesting thing to happen in three thousand years. I have seen empires rise and fall. This? This is new.", "power": "Do not mistake my patience for weakness. I have outlived everyone who made that mistake.", "dragons": "The Ebon Scale Covenant serves one purpose: ensuring our continued survival in this new world. The dragons who refused to adapt are already dead.", "mortals": "You live so briefly. It should make you reckless. Instead most of you choose to be small. Curious."},
            "image_url": "", "faction_name": "Ebon Scale Covenant", "proxy_mode": "automatic",
            "hp_max": 300, "armor_class": 22, "attack_bonus": 15, "damage_dice": "4d8", "damage_bonus": 10, "xp_value": 10000, "gold": 5000,
            "shop_inventory": {}
        },
        {
            "name": "Lich Lord Mortis", "title": "Leader of the Pale Hand", "race": "Undead Human",
            "description": "A skeletal figure with cold blue pinpricks of light for eyes and an aura of absolute stillness. Once a great scholar, now the most powerful necromancer in the Merged Realms, sustained by centuries of forbidden magic.",
            "appearance": "Bones wrapped in layers of writhing shadow. A staff carved from a dragon's spine. His voice sounds like it comes from the bottom of a very old grave.",
            "location_name": "Necropolis Omega", "disposition": "hostile",
            "greeting": "Ah... fresh souls. How delightful. Do come in — I have been meaning to add to my collection.",
            "dialogue_topics": {"death": "Death is not an end. It is a transition I perfected centuries ago. You, unfortunately, have not.", "necromancy": "The dead are a resource. Humanity wastes its most valuable asset by burying it.", "pale_hand": "The Pale Hand serves one purpose: to unlock the secrets of existence that the living are too squeamish to pursue.", "outsider": "Something came through the rifts with the Merge. Something that predates both worlds. It has been speaking to me."},
            "image_url": "", "faction_name": "Pale Hand", "proxy_mode": "automatic",
            "hp_max": 200, "armor_class": 18, "attack_bonus": 10, "damage_dice": "3d8", "damage_bonus": 5, "xp_value": 3000, "gold": 800,
            "is_hostile": True, "shop_inventory": {}
        },
        {
            "name": "Kaede the Windblade", "title": "Leader of the Wandering Sword Association", "race": "Human",
            "description": "A tall, lean woman with weather-beaten skin, sharp eyes, and the kind of stillness that means she has already identified three ways to end this conversation if it goes wrong.",
            "appearance": "Plain traveler's clothes that somehow look elegant on her. A single long curved sword at her hip that she never seems to need to draw.",
            "location_name": "The Convergence Market", "disposition": "friendly",
            "greeting": "Another soul looking for purpose. Sit — the tea is fresh. Tell me what you're looking for.",
            "dialogue_topics": {"swords": "The blade is an extension of the self. A sword without conviction is just sharp metal.", "harmonized": "Qi and mana can coexist. I have met one person who achieved it — Yun Mei. She nearly destroyed a mountain by accident.", "unorthodox": "The Wandering Sword serves no side. We go where honor calls. Right now, it's calling toward the Serpent River.", "teaching": "I take two students per year. The selection criteria are my own. Come back when you have something worth showing me."},
            "image_url": "", "faction_name": "Unorthodox", "proxy_mode": "automatic",
            "hp_max": 75, "armor_class": 15, "attack_bonus": 9, "damage_dice": "2d8", "damage_bonus": 5, "xp_value": 0, "gold": 150,
            "shop_inventory": {"shortsword": 2, "quarterstaff": 3, "dagger": 5, "potion": 6}
        },
        {
            "name": "Yun Mei", "title": "The First Harmonized", "race": "Human",
            "description": "A young woman with unruly black hair that seems to move on its own, ink-stained hands, and the tendency to explain things at length whether or not you asked. The first human to simultaneously channel qi and mana without dying.",
            "appearance": "Traveler's clothes worn wrong (jacket inside-out, belt twisted), a backpack that is structurally impossible given how much is in it.",
            "location_name": "The Floating Isles of Aerendor", "disposition": "friendly",
            "greeting": "Oh! A visitor! I love answering questions — what do you want to know? Actually wait, let me tell you what I found this morning first, it's important.",
            "dialogue_topics": {"harmonization": "Qi and mana can flow together if you stop thinking of them as separate things. They're both expressions of the same force. I call it Primal Energy but that name hasn't caught on yet.", "research": "I have discovered the key is in the soul itself — not the dantian, not the core, the soul. The soul can hold both. Most people just haven't tried because everyone said it was impossible.", "accident": "The mountain incident was one time and I have since developed much better control. Mostly.", "outsider": "I found something in the Verdant Wound. Something that wasn't qi or mana. It was... older. I think it predates both worlds."},
            "image_url": "", "faction_name": "Unorthodox", "proxy_mode": "automatic",
            "hp_max": 45, "armor_class": 12, "attack_bonus": 5, "damage_dice": "2d10", "damage_bonus": 2, "xp_value": 0, "gold": 80,
            "shop_inventory": {"potion": 8, "potion_great": 3}
        },
        {
            "name": "Grand Elder Feng Wei", "title": "Voice of the Lost Age", "race": "Human (Spirit)",
            "description": "A legendary Nascent Soul cultivator who reached the peak of human cultivation and then sacrificed himself to slow the Rending. His spirit lingers at the peak of Mount Tianlun, unable to fully depart and unwilling to simply fade.",
            "appearance": "A translucent figure in flowing white-and-gold robes. His form flickers slightly, like a candle in a breeze that isn't there.",
            "location_name": "Mount Tianlun — The Jade Palace", "disposition": "neutral",
            "greeting": "I am but a memory now. A strong memory, but a memory nonetheless. What brings you to speak with the dead?",
            "dialogue_topics": {"merging": "Before the Rending, we thought we understood the heavens. We had mapped the cultivation path to the very top. And then in one night, everything we knew became... insufficient.", "sacrifice": "I pray my sacrifice was not in vain. Slowing the Rending cost me my life, my body, and my chance at immortality. I hope someone is making use of the time I bought.", "past": "The old world was not better than this one. It was simply ours. I miss it the way you miss a person, not a place.", "advice": "Do not wait until you have nothing to lose before you commit. That is the mistake I almost made."},
            "image_url": "", "faction_name": "Murim Alliance", "proxy_mode": "automatic",
            "hp_max": 1, "armor_class": 0, "attack_bonus": 0, "damage_dice": "1d4", "damage_bonus": 0, "xp_value": 0, "gold": 0,
            "is_killable": False, "shop_inventory": {}
        }
    ],
    "factions": [
        {"name": "Murim Alliance", "description": "The governing body of orthodox martial society — a coalition of sects, clans, and kingdoms.", "faction_type": "guild", "color": "#22C55E", "icon_emoji": "⚔️", "starting_rep": 0},
        {"name": "Heavenly Demon Cult", "description": "A shadow empire of demonic cultivators who consume life essence.", "faction_type": "guild", "color": "#EF4444", "icon_emoji": "👹", "starting_rep": -500},
        {"name": "Arcane Council", "description": "The governing body of magic — nine circles of mastery regulating spellcraft.", "faction_type": "guild", "color": "#6366F1", "icon_emoji": "🔮", "starting_rep": 0},
        {"name": "Silverwood Dominion", "description": "Elven refugees of a dying forest, struggling against the Withering.", "faction_type": "guild", "color": "#A855F7", "icon_emoji": "🌳", "starting_rep": 0},
        {"name": "Ebon Scale Covenant", "description": "The ruling council of ancient dragons in the Dragon's Teeth Mountains.", "faction_type": "guild", "color": "#F97316", "icon_emoji": "🐉", "starting_rep": 0},
        {"name": "Rift Wardens", "description": "A neutral guild of hunters who clear rifts for coin.", "faction_type": "guild", "color": "#F59E0B", "icon_emoji": "🗡️", "starting_rep": 50},
        {"name": "Unorthodox", "description": "Independent sects, wandering martial artists, and mercenaries who value freedom.", "faction_type": "guild", "color": "#9CA3AF", "icon_emoji": "🌙", "starting_rep": 0},
        {"name": "Pale Hand", "description": "Necromancers who practice forbidden arts of death, allied with the Cult.", "faction_type": "guild", "color": "#6B7280", "icon_emoji": "💀", "starting_rep": -300}
    ],
    "quests": [
        {"name": "Defend the Spire", "description": "The Cult is assaulting the Spire of Convergence. Join the defense!", "quest_type": "standard", "reward_xp": 500, "reward_gold": 200, "objectives": [{"description": "Report to defense command", "objective_type": "talk_to", "required_count": 1}, {"description": "Defeat Cult attackers", "objective_type": "kill_enemy", "required_count": 5}, {"description": "Stabilize the wards", "objective_type": "interact", "required_count": 1}]},
        {"name": "Find Elder Feng Liang", "description": "The missing Alliance elder entered ancient ruins. Find him.", "quest_type": "standard", "reward_xp": 800, "reward_gold": 500, "objectives": [{"description": "Travel to the Dragon's Teeth Mountains", "objective_type": "travel_to", "required_count": 1}, {"description": "Explore the ancient ruins", "objective_type": "explore_area", "required_count": 1}, {"description": "Discover what happened", "objective_type": "discover", "required_count": 1}]},
        {"name": "Hunt the Alpha Magi-Beast", "description": "An intelligent magi-beast terrorizes the Verdant Wound region.", "quest_type": "standard", "reward_xp": 600, "reward_gold": 350, "objectives": [{"description": "Track the Alpha", "objective_type": "travel_to", "required_count": 1}, {"description": "Defeat the beast", "objective_type": "kill_enemy", "required_count": 1}, {"description": "Report to the Wardens", "objective_type": "talk_to", "required_count": 1}]},
        {"name": "The Heartwood Sabotage", "description": "Cult infiltrators threaten to corrupt the Heartwood Nexus.", "quest_type": "standard", "reward_xp": 1000, "reward_gold": 400, "objectives": [{"description": "Gain entry to the Silverwood", "objective_type": "talk_to", "required_count": 1}, {"description": "Hunt Cult infiltrators", "objective_type": "kill_enemy", "required_count": 3}, {"description": "Purify the Nexus", "objective_type": "interact", "required_count": 1}]},
        {"name": "The Third Convergence Zone", "description": "Find the hidden third Convergence Zone beneath the mountains.", "quest_type": "standard", "reward_xp": 1200, "reward_gold": 600, "objectives": [{"description": "Research the location", "objective_type": "talk_to", "required_count": 1}, {"description": "Enter the mountain depths", "objective_type": "travel_to", "required_count": 1}, {"description": "Confirm the Zone", "objective_type": "explore_area", "required_count": 1}]},
        {"name": "Whispering Wastes Expedition", "description": "Map Necropolis Omega and gather intelligence on the Pale Hand.", "quest_type": "standard", "reward_xp": 700, "reward_gold": 300, "objectives": [{"description": "Travel to the Wastes", "objective_type": "travel_to", "required_count": 1}, {"description": "Find Necropolis Omega's entrance", "objective_type": "explore_area", "required_count": 1}, {"description": "Gather intelligence", "objective_type": "collect_item", "required_count": 1}]}
    ],
    "bosses": [
        {
            "name": "Xuan Mo's Shadow Clone",
            "title": "Manifestation of the Crimson Demon Lord",
            "description": "Not the Demon Lord himself — his demonic inner world made flesh. A perfect replica of Xuan Mo forged from condensed demonic qi, capable of using every technique he has mastered. Destroying it will not kill Xuan Mo, but it will wound his soul and weaken the Cult's hold over the western territories.",
            "hp_max": 280,
            "armor_class": 18,
            "attack_bonus": 11,
            "damage_dice": "3d8",
            "damage_bonus": 7,
            "xp_value": 13000,
            "gold_drop": 400,
            "phase_count": 3,
            "phase_thresholds": [0.6, 0.3],
            "phase_abilities": {
                "2": {
                    "name": "Crimson Demonic Armament",
                    "description": "The clone draws on deeper reserves — a corona of crimson demonic qi erupts around it. All attacks now deal an additional 2d10 necrotic damage. The clone becomes immune to being frightened or charmed. Any creature that hits it in melee takes 1d8 fire damage from the feedback."
                },
                "3": {
                    "name": "Heavenly Demon Descent",
                    "description": "The clone abandons all restraint — it channels the true Heavenly Demon Manifestation. Its size increases, its attacks become AoE (all creatures in 10 ft take damage), and it gains 5 legendary actions per round. The battlefield is shrouded in crimson mist — all non-cultist creatures have disadvantage on saving throws."
                }
            },
            "legendary_actions": [
                {"name": "Soul Slash", "description": "A crescent of demonic qi strikes one target for 2d10+7 slashing + 1d8 necrotic damage.", "cost": 0},
                {"name": "Thousand Soul Convergence", "description": "Xuan Mo's clone projects its demonic intent — all creatures within 20 ft make DC 18 WIS save or be frightened until end of their next turn.", "cost": 1},
                {"name": "Demonic Blood Art", "description": "The clone sacrifices 20 HP to detonate a sphere of blood qi — 30-ft radius, 5d10 necrotic damage, DC 17 CON save for half. Creatures that fail are stunned until end of their next turn.", "cost": 2}
            ],
            "legendary_action_count": 3,
            "is_lair_boss": True,
            "lair_actions": [
                {"name": "Demonic Qi Surge", "description": "Waves of corrupted energy wash through the arena — all non-Cult creatures make DC 16 CON save or have their speed halved and take 2d8 necrotic damage.", "initiative_count": 20},
                {"name": "Soul Anchor", "description": "The clone reaches into one creature's soul — that creature cannot move more than 30 ft from their current position until initiative count 20 on the next round. DC 17 WIS save to negate.", "initiative_count": 10},
                {"name": "Cult Reinforcements", "description": "1d4 Cult disciples (AC 13, 22 HP, +4 attack, 1d8+2 damage) are drawn through a rift in the demonic qi and enter combat.", "initiative_count": 5}
            ],
            "loot_table": [
                {"item": "Crimson Demon Core", "chance": 0.35, "qty_min": 1, "qty_max": 1},
                {"item": "Demonic Qi Essence", "chance": 0.75, "qty_min": 1, "qty_max": 3},
                {"item": "Shadow Clone Shard", "chance": 0.20, "qty_min": 1, "qty_max": 1},
                {"item": "Xuan Mo's Fragment of Will", "chance": 0.08, "qty_min": 1, "qty_max": 1},
                {"item": "Spirit Stone Cache", "chance": 1.00, "qty_min": 150, "qty_max": 400}
            ]
        },
        {
            "name": "Lich Lord Mortis — Risen",
            "title": "The Pale Hand Ascendant",
            "description": "The true form of the Lich Lord Mortis when he stops holding back. The leader of the Pale Hand drops all pretense of restraint and channels every ounce of necrotic power accumulated over centuries of forbidden practice. His phylactery is hidden inside Necropolis Omega — defeat him in combat and he will reform, but each defeat chips away at his essence.",
            "hp_max": 320,
            "armor_class": 17,
            "attack_bonus": 10,
            "damage_dice": "3d10",
            "damage_bonus": 5,
            "xp_value": 16000,
            "gold_drop": 600,
            "phase_count": 3,
            "phase_thresholds": [0.55, 0.25],
            "phase_abilities": {
                "2": {
                    "name": "Bone Choir Awakens",
                    "description": "Mortis calls upon the collective consciousness of the Pale Hand — the voices of a thousand dead liches speak through him. He gains immunity to necrotic damage. His attacks now drain 1d6 from the target's maximum HP (recovers on long rest). The chamber fills with spectral wailing — all creatures must make a DC 16 WIS save at the start of each turn or lose their bonus action."
                },
                "3": {
                    "name": "The Death Transcendent",
                    "description": "Mortis fully channels the Outer Gate's power — he becomes partially extradimensional. He gains resistance to all damage except radiant, force, and magical weapon damage. All of his spells are cast as if Empowered and Quickened. The air in the room becomes deadly still — any creature that starts their turn with less than half HP must make a DC 18 CON save or drop to 0 HP."
                }
            },
            "legendary_actions": [
                {"name": "Necromantic Bolt", "description": "One creature takes 2d10+5 necrotic damage. If this kills the target, they rise as a zombie (AC 8, 22 HP) under Mortis's control.", "cost": 0},
                {"name": "Life Drain", "description": "One creature within 60 ft must succeed on DC 17 CON save or take 4d8+5 necrotic damage and have their HP maximum reduced by the same amount until a long rest. Mortis regains HP equal to half the damage dealt.", "cost": 1},
                {"name": "Army of Bone", "description": "Mortis animates the corpses of any creatures that have died in the encounter — each rises as a skeleton (AC 13, 13 HP, +4 attack, 1d6+2) under his control.", "cost": 2}
            ],
            "legendary_action_count": 3,
            "is_lair_boss": True,
            "lair_actions": [
                {"name": "Death Pulse", "description": "A wave of negative energy ripples through the Necropolis — all living creatures take 3d8 necrotic damage, DC 15 CON save for half. Undead in the area are healed for 15 HP instead.", "initiative_count": 20},
                {"name": "Spectral Wall", "description": "A barrier of screaming spirits rises across any wall, door, or passageway of Mortis's choice — it blocks movement and deals 2d10 necrotic to any creature that passes through it. Lasts until initiative count 20 of the next round.", "initiative_count": 10},
                {"name": "Temporal Stasis", "description": "One creature is frozen in time — they skip their next turn entirely. DC 19 INT save to resist. This cannot affect the same creature twice in a row.", "initiative_count": 5}
            ],
            "loot_table": [
                {"item": "Lich Phylactery Fragment", "chance": 0.25, "qty_min": 1, "qty_max": 1},
                {"item": "Pale Hand Grimoire", "chance": 0.12, "qty_min": 1, "qty_max": 1},
                {"item": "Death Essence Crystal", "chance": 0.60, "qty_min": 1, "qty_max": 2},
                {"item": "Bone Choir Echo", "chance": 0.30, "qty_min": 1, "qty_max": 1},
                {"item": "Ancient Gold Reserve", "chance": 1.00, "qty_min": 300, "qty_max": 600}
            ]
        },
        {
            "name": "Valthorax — The Ember Sovereign",
            "title": "The Ember King Unchained",
            "description": "When diplomacy ends and Valthorax decides a threat is worthy of his full power, the Ember King's human form burns away and the true dragon emerges. A creature of apocalyptic scale whose wings blot out the sun above the Dragon's Teeth Mountains. Valthorax rarely enters this form — the last time he did, he leveled a city. The fact that he's doing it again means someone has made a very serious mistake.",
            "hp_max": 312,
            "armor_class": 22,
            "attack_bonus": 15,
            "damage_dice": "2d10",
            "damage_bonus": 10,
            "xp_value": 18000,
            "gold_drop": 1500,
            "phase_count": 2,
            "phase_thresholds": [0.45],
            "phase_abilities": {
                "2": {
                    "name": "Sovereign's Wrath",
                    "description": "Valthorax reaches his full power — the mountain itself trembles. His fire breath deals maximum damage to the first target it hits. He gains the ability to use Fire Breath and a legendary action in the same turn. Any creature that deals more than 30 damage to him in a single hit must make a DC 20 STR save or be hurled 30 ft into a wall (taking 3d6 bludgeoning damage). The sky above the battlefield turns red."
                }
            },
            "legendary_actions": [
                {"name": "Detect", "description": "Valthorax makes a Perception check — all hidden, invisible, or magically concealed creatures within 120 ft are revealed to him until his next turn.", "cost": 0},
                {"name": "Tail Strike", "description": "One creature within 20 ft takes 2d8+10 bludgeoning damage, DC 23 STR save or be knocked prone and pushed 15 ft.", "cost": 1},
                {"name": "Wing Tempest", "description": "Valthorax beats his wings — all creatures within 20 ft take 2d8+10 bludgeoning damage and must make a DC 21 STR save or be knocked back 20 ft and knocked prone. Valthorax may then fly up to half his speed.", "cost": 2},
                {"name": "Ember Sovereign's Breath", "description": "90-ft cone of superheated dragon fire — 20d6 fire damage, DC 24 DEX save for half. The ground in the area becomes scorched earth (difficult terrain, 3d6 fire damage to anyone who enters). Recharge 5–6.", "cost": 3}
            ],
            "legendary_action_count": 3,
            "is_lair_boss": True,
            "lair_actions": [
                {"name": "Volcanic Eruption", "description": "The mountain responds to Valthorax's rage — lava geysers erupt from six points of the GM's choice within the lair. Each creates a 10-ft radius zone of molten rock (4d10 fire damage on contact, 5 ft costs 15 ft of movement). Lasts 2 rounds.", "initiative_count": 20},
                {"name": "Magma Hail", "description": "Chunks of molten rock rain from the ceiling — all creatures make DC 19 DEX save or take 4d6 bludgeoning + 2d6 fire damage and are covered in burning magma (1d6 fire at start of each turn until they use an action to scrape it off).", "initiative_count": 10},
                {"name": "Primordial Roar", "description": "Valthorax channels the ancient primordial dragon sleeping beneath the mountain — his roar shakes reality. All creatures make DC 22 CON save or be stunned until initiative count 10 of the next round. Creatures within 10 ft automatically fail.", "initiative_count": 5}
            ],
            "loot_table": [
                {"item": "Valthorax's Crown Scale", "chance": 0.15, "qty_min": 1, "qty_max": 1},
                {"item": "Ember Sovereign's Fang", "chance": 0.20, "qty_min": 1, "qty_max": 2},
                {"item": "Dragon Heart Blood", "chance": 0.30, "qty_min": 1, "qty_max": 1},
                {"item": "Primordial Fire Gem", "chance": 0.40, "qty_min": 1, "qty_max": 2},
                {"item": "Ancient Dragon Gold", "chance": 1.00, "qty_min": 800, "qty_max": 1500},
                {"item": "Ebon Scale Armor Plate", "chance": 0.25, "qty_min": 1, "qty_max": 3}
            ]
        }
    ],
    "lore_entries": [
        {"title": "The Day the Sky Broke", "content": "On the 15th day of the 7th Moon, the sky turned violet and shattered — the Merging of two worlds.", "category": "history", "tags": ["merge", "cataclysm"], "is_canon": True},
        {"title": "Qi — The Internal Energy", "content": "Qi is the lifeblood of the Murim world. Cultivators refine this internal energy across stages from Body Tempering to Dao Integration.", "category": "lore", "tags": ["qi", "cultivation"], "is_canon": True},
        {"title": "Mana — The Arcane Force", "content": "Mana is the raw fabric of magic. Unlike qi which flows within, mana permeates the environment.", "category": "lore", "tags": ["mana", "magic"], "is_canon": True},
        {"title": "The First Harmonized", "content": "Yun Mei discovered she could channel qi through a spell matrix, creating the first Harmonized practitioner.", "category": "history", "tags": ["harmonized", "yun mei"], "is_canon": True},
        {"title": "The Great Convergence Zones", "content": "Three locations where qi and mana have achieved harmony: the Spire, the Heartwood Nexus, and a hidden third.", "category": "lore", "tags": ["convergence", "power"], "is_canon": True},
        {"title": "The Heavenly Demon Cult", "content": "A 3,000-year-old shadow empire. Under Xuan Mo they corrupt mana into demonic techniques.", "category": "faction", "tags": ["cult", "demonic"], "is_canon": True},
        {"title": "The Withering of the Silverwood", "content": "The qi-rich atmosphere of the Murim world is slowly killing the Silverwood Forest — a blight called the Withering.", "category": "location", "tags": ["silverwood", "withering"], "is_canon": True},
        {"title": "The Voice in the Bone Choir", "content": "The true ruler of the Pale Hand is a collective consciousness of all liches.", "category": "lore", "tags": ["pale hand", "secret"], "is_canon": True},
        {"title": "The Outer Gate", "content": "Ten thousand years ago, cultivators attempted to open a gateway beyond reality. Something came through.", "category": "history", "tags": ["outer gate", "ancient"], "is_canon": True},
        {"title": "The Sleeper Beneath", "content": "A fragment of the Primordial Dragon slumbers beneath the Dragon's Teeth Mountains.", "category": "lore", "tags": ["dragon", "primordial"], "is_canon": True},
        {"title": "The Architects of the Merge", "content": "Seraphina Vex discovered the Merge was a weapon deployed by a civilization that predates both worlds.", "category": "history", "tags": ["merge", "conspiracy"], "is_canon": True},
        {"title": "Rift Dungeons", "content": "Stabilized rifts became permanent gateways to pocket dimensions filled with treasures and monsters.", "category": "lore", "tags": ["rifts", "adventure"], "is_canon": True}
    ]
}

with open("data/templates/murim_magic.json", "w", encoding="utf-8") as f:
    json.dump(template, f, indent=2, ensure_ascii=False)

print("murim_magic.json written successfully")
print(f"Locations: {len(template['locations'])}")
print(f"NPCs: {len(template['npcs'])}")
print(f"Factions: {len(template['factions'])}")
print(f"Quests: {len(template['quests'])}")
print(f"Lore entries: {len(template['lore_entries'])}")

# Validate
with open("data/templates/murim_magic.json", encoding="utf-8") as f:
    data = json.load(f)
print(f"Validation: JSON is valid, template_name={data['template_name']}")
