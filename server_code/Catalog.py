"""The task catalogue: every kind of neighbourly job a bounty can be, with suggested prices and the default
quality checklist. Also what is never allowed. The pages get it all through get_catalog().

Prices are the suggested BASE bounty in Canadian dollars for a small / medium / large job. MIN_BASE is
enforced on the server (Trust.check_amounts), whatever the page sends.
Months (1-12) say when a task is in season (Montréal), for the "In season" chips.
"""
import anvil.server

MIN_BASE = 20
MAX_BASE = 500
MAX_BONUS = 200

CATEGORIES = [
    {"key": "yard", "name": "Yard & garden", "icon": "leaf"},
    {"key": "snow", "name": "Snow & ice", "icon": "snow"},
    {"key": "junk", "name": "Junk & garbage", "icon": "bin"},
    {"key": "moving", "name": "Moving & lifting", "icon": "box"},
    {"key": "cleaning", "name": "Outdoor cleaning", "icon": "spray"},
    {"key": "errands", "name": "Errands & tech help", "icon": "bag"},
    {"key": "pets", "name": "Pets & plants", "icon": "paw"},
    {"key": "handy", "name": "Seasonal & handy", "icon": "wrench"},
    {"key": "other", "name": "Something else", "icon": "sparkle"},
]

ALL_YEAR = list(range(1, 13))


def _t(key, cat, name, blurb, prices, months, checklist, vehicle=False, tools=""):
    return {"key": key, "cat": cat, "name": name, "blurb": blurb, "prices": list(prices), "months": months,
            "checklist": checklist, "vehicle": vehicle, "tools": tools}


TASKS = [
    # ---- yard & garden
    _t("leaves", "yard", "Rake & bag leaves", "Rake the lawn and beds, bag the leaves in paper yard bags, out to the curb.",
       (20, 40, 70), [9, 10, 11],
       ["Lawn raked clear of leaves", "Garden beds cleared", "Leaves bagged in paper yard bags", "Bags placed at the curb",
        "Walkway and steps swept"], tools="Rake and bags provided by the poster, unless the bounty says otherwise."),
    _t("mow", "yard", "Mow the lawn", "Mow front and/or back lawn and trim the edges.", (25, 40, 60), [5, 6, 7, 8, 9],
       ["Whole lawn mowed evenly", "Edges trimmed along paths and beds", "Clippings bagged or mulched", "Paths swept clean"]),
    _t("weeds", "yard", "Weed garden beds", "Pull weeds from beds and between paving stones.", (20, 35, 60), [5, 6, 7, 8, 9],
       ["Weeds pulled with the roots", "Beds left tidy (no plants damaged)", "Weeds bagged and removed", "Cracks in the paving cleared"]),
    _t("planting", "yard", "Plant flowers or bulbs", "Plant flowers, bulbs or vegetables where you show them.", (20, 35, 55), [4, 5, 6, 9, 10],
       ["Everything planted where asked", "Planted at the right depth", "Watered in", "Pots and bags cleaned up"]),
    _t("hedges", "yard", "Trim hedges & bushes", "Trim hedges and bushes from the ground (no ladders above 2 m).", (25, 45, 80), [5, 6, 7, 8, 9],
       ["Hedges trimmed to the shape asked", "Ground-level only (no tall ladders)", "Clippings raked up", "Clippings bagged or removed"],
       tools="Trimmer provided by the poster, unless the bounty says otherwise."),
    _t("springclean", "yard", "Spring yard clean-up", "Rake out winter debris, pick up branches, wake the garden up.", (30, 55, 90), [4, 5],
       ["Lawn raked of dead grass and debris", "Branches and twigs picked up", "Beds cleared of last year's growth",
        "Everything bagged at the curb", "Paths swept"]),
    _t("watering", "yard", "Water plants while I'm away", "Drop by and water the garden and pots on the days you agree.", (20, 30, 50), [5, 6, 7, 8, 9],
       ["Came on every agreed day", "Every pot and bed watered", "Hose and tools put back", "Sent a photo each visit"]),
    # ---- snow & ice
    _t("driveway", "snow", "Shovel a driveway", "Clear the driveway after a snowfall, down to the pavement.", (25, 40, 65), [11, 12, 1, 2, 3, 4],
       ["Driveway cleared edge to edge", "End of the driveway (plow ridge) cleared", "Snow piled where it won't slide back",
        "No snow thrown onto the sidewalk or street"], tools="Shovel provided by the poster, unless the bounty says otherwise."),
    _t("sidewalk", "snow", "Clear sidewalk & steps", "Shovel the walk, the front steps and the balcony stairs.", (20, 30, 45), [11, 12, 1, 2, 3, 4],
       ["Walkway cleared down to the pavement", "Front steps cleared", "Outdoor stairs cleared", "Salt or grit spread on icy spots"]),
    _t("digout", "snow", "Dig out a snowed-in car", "Brush off and dig out a car the plow buried.", (20, 30, 45), [11, 12, 1, 2, 3],
       ["Car brushed off (roof, windows, lights)", "Snow cleared around all four wheels", "Plow ridge in front cleared", "No scratches on the car"]),
    _t("salt", "snow", "Salt & de-ice walkways", "Spread salt or grit on icy paths and stairs.", (20, 25, 35), [11, 12, 1, 2, 3, 4],
       ["Every path salted or gritted", "Stairs done", "Ice chipped where it was thick", "Salt bag closed and stored"]),
    _t("balcony", "snow", "Clear a balcony or deck", "Shovel a ground-floor or second-floor balcony, deck or patio (never the roof).", (20, 35, 50),
       [12, 1, 2, 3], ["Balcony or deck cleared", "Snow not dropped on anyone's car or path", "Railings brushed off", "No roof climbing"]),
    # ---- junk & garbage
    _t("curb", "junk", "Garbage & recycling to the curb", "Take the bins to the curb on collection night and bring them back.", (20, 20, 30), ALL_YEAR,
       ["Bins out on the right night", "Recycling sorted into the right bin", "Bins brought back after pickup", "Lids closed, nothing spilled"]),
    _t("ecocentre", "junk", "Haul junk to the eco-centre", "Load up old stuff and drop it at the eco-centre (needs a car or truck).",
       (40, 70, 120), ALL_YEAR, ["Everything on the list taken away", "Dropped at an eco-centre (no dumping)",
                                 "Receipt or photo of the drop-off", "Area left swept"], vehicle=True),
    _t("bins", "junk", "Wash the bins", "Hose out and scrub the garbage, recycling and compost bins.", (20, 25, 35), [5, 6, 7, 8, 9],
       ["Every bin washed inside and out", "No smell left", "Water drained away from the house", "Bins put back"]),
    _t("litter", "junk", "Pick up litter", "Pick up litter around the property, the alley or a stretch of street.", (20, 30, 45), [4, 5, 6, 7, 8, 9, 10],
       ["The whole agreed area covered", "Litter bagged", "Recyclables sorted out", "Bags left at the curb"]),
    _t("boxes", "junk", "Break down boxes after a move", "Flatten and bundle cardboard boxes and packing for recycling.", (20, 30, 45), ALL_YEAR,
       ["Every box flattened", "Bundled or in the recycling bin", "Packing foam and plastic sorted", "Floor left clear"]),
    # ---- moving & lifting
    _t("furniture", "moving", "Move heavy furniture", "Move furniture between rooms or floors. Two people for the big stuff.", (30, 60, 100), ALL_YEAR,
       ["Every piece moved where asked", "No damage to walls or floors", "Furniture put back together if taken apart", "Packing removed"]),
    _t("truck", "moving", "Load or unload a moving truck", "Carry boxes and furniture to or from a rented truck.", (40, 80, 150), ALL_YEAR,
       ["Truck loaded or unloaded completely", "Heavy items at the bottom", "Nothing broken", "Boxes in the right rooms"]),
    _t("basement", "moving", "Carry things to the basement or storage", "Shift boxes, bikes or patio furniture into storage.", (20, 35, 55), ALL_YEAR,
       ["Everything moved to the right place", "Stacked safely", "Paths left clear", "Nothing damaged"]),
    _t("flatpack", "moving", "Assemble flat-pack furniture", "Put together that bookcase, bed or desk (instructions included).", (25, 45, 80), ALL_YEAR,
       ["Built following the instructions", "Sturdy, nothing wobbles", "Anchored to the wall if the kit says so", "Packaging taken out"]),
    # ---- outdoor cleaning
    _t("windows", "cleaning", "Wash ground-floor windows", "Wash outside windows you can reach from the ground.", (25, 40, 60), [4, 5, 6, 7, 8, 9, 10],
       ["Every ground-floor window washed", "No streaks", "Screens and sills wiped", "No ladder above 2 m"]),
    _t("carwash", "cleaning", "Wash a car", "Hand wash and dry a car, vacuum the inside.", (20, 35, 50), [4, 5, 6, 7, 8, 9, 10],
       ["Outside washed and dried", "Windows clean inside and out", "Inside vacuumed", "Tires and rims rinsed"]),
    _t("patio", "cleaning", "Sweep & hose a patio or balcony", "Sweep, scrub and hose down a patio, deck or balcony.", (20, 30, 45), [4, 5, 6, 7, 8, 9],
       ["Swept clean", "Stains scrubbed", "Rinsed down", "Furniture put back"]),
    _t("garage", "cleaning", "Clean out a garage or shed", "Sort, sweep and organise a garage or shed.", (40, 70, 120), [4, 5, 6, 7, 8, 9, 10],
       ["Everything sorted into keep / donate / toss", "Floor swept", "Shelves organised", "Trash bagged at the curb"]),
    # ---- errands & tech help
    _t("pickup", "errands", "Pick up a prepaid order", "Collect a prepaid grocery or store order and bring it home. No buying for anyone.",
       (20, 25, 35), ALL_YEAR, ["Order collected (already paid by the poster)", "Brought home on time", "Cold things kept cold",
                                "Receipt handed over"]),
    _t("dropoff", "errands", "Drop off donations or returns", "Take bags to a donation centre, books to the library, a parcel to the post office.",
       (20, 25, 40), ALL_YEAR, ["Everything dropped off", "Receipt or photo of the drop-off", "Nothing left in the car", "Done on time"]),
    _t("techhelp", "errands", "Tech help at home", "Set up a phone, TV, printer or Wi-Fi, explained in plain words.", (20, 35, 60), ALL_YEAR,
       ["The device works as asked", "Explained how to use it", "Passwords written down for the owner only", "Nothing installed without asking"]),
    _t("pictures", "errands", "Hang pictures, mirrors & shelves", "Hang frames and light shelves with the right anchors.", (20, 35, 55), ALL_YEAR,
       ["Hung level where asked", "Right anchors for the wall", "Dust and packaging cleaned up", "Nothing over 20 kg"]),
    # ---- pets & plants
    _t("dogwalk", "pets", "Walk a dog", "Walk the dog for 30-60 minutes, on leash, poop bags in hand.", (20, 25, 40), ALL_YEAR,
       ["Walked for the agreed time", "On leash the whole time", "Picked up after the dog", "Water bowl filled after"]),
    _t("petvisit", "pets", "Pet drop-in visit", "Feed the cat, change the litter, a little playtime while the owners are away.", (20, 30, 50), ALL_YEAR,
       ["Came at the agreed times", "Food and fresh water given", "Litter or cage cleaned", "Sent a photo of the pet"]),
    _t("poop", "pets", "Yard poop patrol", "Scoop the yard after the dog (or after the winter thaw).", (20, 25, 40), [3, 4, 5, 6, 7, 8, 9, 10],
       ["The whole yard covered", "Bagged and in the garbage", "Tools rinsed", "Gate closed after"]),
    _t("plantsit", "pets", "House-plant sitting", "Water indoor plants while the owners travel.", (20, 30, 45), ALL_YEAR,
       ["Every plant watered as asked", "Came on every agreed day", "No spills on the floor", "Doors locked after"]),
    # ---- seasonal & handy
    _t("lights", "handy", "Holiday lights up or down", "Put up or take down holiday lights you can reach from the ground.", (25, 45, 70), [11, 12, 1],
       ["Lights up or down where asked", "Every strand tested", "Cables safe from tripping", "No roof climbing"]),
    _t("ac", "handy", "Install or remove a window AC", "Lift a window air conditioner in or out (two people).", (30, 45, 60), [5, 6, 9, 10],
       ["Unit in or out safely", "Window sealed or closed after", "Brackets used if the kit has them", "Unit stored or plugged in"]),
    _t("tempo", "handy", "Car shelter up or down", "Put up or take down a winter car shelter (Tempo).", (40, 60, 90), [10, 11, 4],
       ["Frame put up or taken down", "Canvas tight with no tears made", "Anchors set or pulled", "Parts stored together"]),
    _t("firewood", "handy", "Stack firewood", "Carry and stack a delivery of firewood.", (25, 45, 70), [9, 10, 11],
       ["All the wood carried", "Stacked neat and stable", "Off the ground or on pallets", "Bark and chips swept"]),
    _t("bbq", "handy", "Assemble a BBQ or patio set", "Put together a barbecue, patio set or garden shed kit.", (30, 50, 80), [4, 5, 6, 7],
       ["Built following the instructions", "Every bolt tightened", "No gas connections (left to the owner)", "Packaging taken out"]),
    _t("paint", "handy", "Paint a fence or deck", "Scrape and paint or stain a fence, deck or shed.", (50, 90, 160), [5, 6, 7, 8, 9],
       ["Old flakes scraped off", "Even coat with no drips", "Plants and paths covered while painting", "Brushes cleaned and lids closed"]),
    _t("other", "other", "Another neighbourly task", "Something else a neighbour can do without a licence. A moderator checks it first.",
       (20, 40, 70), ALL_YEAR, ["Done as described", "Area left clean", "Done on time", "Nothing damaged"]),
]

TASK_BY_KEY = {t["key"]: t for t in TASKS}

SIZES = [{"key": "small", "name": "Small", "hint": "Under an hour"},
         {"key": "medium", "name": "Medium", "hint": "1 to 3 hours"},
         {"key": "large", "name": "Large", "hint": "Half a day or more"}]
SIZE_INDEX = {"small": 0, "medium": 1, "large": 2}

PAY_METHODS = [{"key": "cash", "name": "Cash on the spot"},
               {"key": "etransfer", "name": "Interac e-Transfer"},
               {"key": "either", "name": "Cash or e-Transfer"}]

# Shown on the rules page and in the post form. The text scanner (Trust.scan) watches for them too.
NOT_ALLOWED = [
    "Anything that needs a licence: electrical, plumbing, gas, roofing, tree felling, pest control",
    "Work on roofs, or on ladders above 2 m",
    "Childcare, elder care, rides in your car, or anything with medicine",
    "Buying things with the helper's own money, gift cards, crypto, or money transfers",
    "Carrying sealed packages for someone you don't know",
    "Hazardous waste: asbestos, chemicals, propane, paint thinner, needles",
    "Anything illegal, unsafe, or that a neighbour wouldn't proudly do in daylight",
]


SKILLS = ["Strong back", "Own car", "Own truck or van", "Own tools", "Own snow shovel", "Own lawn mower", "Pet lover",
          "Tech savvy", "Early bird", "Weekends", "Evenings", "Bilingual (EN/FR)"]


def task(key):
    return TASK_BY_KEY.get(key)


def suggested(key, size):
    t = TASK_BY_KEY.get(key) or TASK_BY_KEY["other"]
    return t["prices"][SIZE_INDEX.get(size, 1)]


@anvil.server.callable
def get_catalog():
    """Everything the pages need to describe tasks (public, never changes while the app runs)."""
    return {"categories": CATEGORIES, "tasks": TASKS, "sizes": SIZES, "pay_methods": PAY_METHODS,
            "not_allowed": NOT_ALLOWED, "skills": SKILLS, "min_base": MIN_BASE, "max_base": MAX_BASE, "max_bonus": MAX_BONUS}
