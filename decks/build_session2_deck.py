"""Build the Session 2 deck: build it end to end.

Run from the repository root::

    python decks/build_session2_deck.py

Output lands in decks/out/. Slide count is asserted at the end so a page
numbering drift fails the build rather than shipping quietly.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from theme import (  # noqa: E402
    AMBER, BLUE, BRONZE, COPPER, GOLD, GREEN, RED, SILVER,
    bullets_slide, cards_slide, closing_slide, code_slide, compare_slide,
    flow_slide, medallion_slide, new_deck, notes, quote_slide, save,
    section_slide, steps_slide, summarise, table_slide, title_slide,
)

TOTAL = 44
_page = 0


def page() -> int:
    global _page
    _page += 1
    return _page


def build():
    prs = new_deck()

    # ---------------------------------------------------------------- 1
    s = title_slide(
        prs,
        "Build it end to end",
        "Session 2  ·  Imagery to a map a planner can filter",
        "JDI Woodlands  ·  Four hours  ·  Five steps, one scheduled pipeline, one honest conversation about AI",
        "Session 2 of 2  ·  You need the workspace and the stand register from Session 1",
        icon_row=["satellite", "filter", "brain", "chart", "pipeline", "forest"],
    )
    notes(s, """
Today is the build. Session 1 was foundations, and if anyone missed it, pair them with someone
who did not, because we do not have time to rebuild a workspace this morning.

Set expectations in the first minute: by the end of today there is a pipeline that runs on a
schedule with nobody watching it. Not a notebook someone runs. That distinction is the whole
point of the day.

Say plainly that the hard part today is not the imagery. It is the discipline about what each
layer is allowed to do, and the twenty minutes we spend on where AI is quietly wrong.
""")

    # ---------------------------------------------------------------- 2
    s = quote_slide(
        prs,
        "Woodlands planning needs a monthly, stand-level view of forest condition:\n"
        "which stands are softwood, hardwood or mixedwood, which have been harvested\n"
        "since the last look, and which are showing moisture stress.",
        "It must refresh without anyone opening a notebook, and a planner must be able to filter it on a map.",
        accent=GREEN, icon="target", page=page(), total=TOTAL,
    )
    notes(s, """
Read it once, slowly, then leave it on screen for a beat.

This paragraph is the spine of the day. Every time someone proposes an addition, and they will,
the test is whether it serves this sentence. Most proposals do not, and saying so out loud is
the most useful thing a lead does on a project like this.

Point at the second line specifically. "Without anyone opening a notebook" is the requirement
that separates a demo from a product, and it is the reason Step 5 exists.
""")

    # ---------------------------------------------------------------- 3
    s = table_slide(
        prs, "Running order",
        ["Time", "Block", "Min"],
        [
            ["0:00", "Homework debrief and today's problem statement", "15"],
            ["0:15", "Step 1, get the imagery: Planetary Computer and STAC", "45"],
            ["1:00", "Step 2, analyse it: GeoPandas and Copilot", "50"],
            ["1:50", "Break", "15"],
            ["2:05", "Step 3, add AI where it earns its place, and where it is quietly wrong", "45"],
            ["2:50", "Step 4, publish it: Delta, Direct Lake, Power BI", "45"],
            ["3:35", "Step 5, make it repeatable, assignment, office hours", "25"],
        ],
        widths=[0.9, 6.5, 0.7],
        kicker="Agenda", icon="clock", page=page(), total=TOTAL,
        footnote="Four checkpoints. Each one has a solution notebook. Using it is the designed path.",
    )
    notes(s, """
Flag the break now. A room that does not know when the break is takes its own break, one person
at a time, during the block you most needed them awake for.

The five steps map one to one onto the five notebooks. Say that, because it makes the deck and
the repo navigable without anyone asking.
""")

    # ---------------------------------------------------------------- 4
    s = steps_slide(
        prs, "Homework debrief",
        [
            ("Three volunteers, two minutes each",
             "Show the area of interest you chose and the row count you landed. No slides, just the notebook.",
             "6 min"),
            ("What went wrong",
             "The bounding box, almost always. Reversed corners or a dropped minus sign on the longitude.",
             "4 min"),
            ("What surprised you",
             "Usually the cloud. The month you wanted had no clear scene, which is the real problem this "
             "pipeline exists to handle.", "3 min"),
            ("Park the rest",
             "Anything unresolved goes in the channel and gets picked up in office hours at 3:50.",
             "2 min"),
        ],
        kicker="0:00", icon="people", page=page(), total=TOTAL,
    )
    notes(s, """
Keep this tight. It is fifteen minutes and it will eat thirty if you let it.

The cloud point is worth drawing out. Someone will have picked a month with no usable scene and
concluded they did something wrong. They did not. That is the production problem, and we design
for it in Step 5.
""")

    # ---------------------------------------------------------------- 5
    s = medallion_slide(
        prs, "The contracts you agreed in Session 1",
        ["Scene catalogue, one row per scene, unsigned hrefs",
         "Raw windowed rasters, native projection, nothing masked",
         "Append only, every run tagged with a pipeline_run_id"],
        ["Reprojected once to EPSG:2953, cloud and shadow masked",
         "Spectral indices computed, NDVI, NDMI, NBR",
         "One row per stand per scene date"],
        ["Classified stands with a confidence and a threshold you can point at",
         "Star schema, facts and dimensions, ready for Direct Lake",
         "AI narrative, validated against the source row"],
        kicker="Recap", page=page(), total=TOTAL,
        footnote="Three workspaces, one per layer. A mistake in silver cannot overwrite bronze.",
    )
    notes(s, """
Thirty seconds per layer, no more. This is a recap, not a re-teach.

The line worth repeating is that bronze does not make decisions. Every reprojection, every mask,
every threshold is a decision, and the moment you make one in bronze you have lost the ability to
change your mind later without going back to the network.

Point at the footnote and remind them the three workspaces are why their notebooks read through
shortcuts today.
""")

    # ---------------------------------------------------------------- 6
    s = section_slide(prs, 1, "Get the imagery",
                      "Planetary Computer, STAC, and why a catalogue beats a file share",
                      icon="satellite", accent=BRONZE, duration="45 min")
    notes(s, """
Notebook 01. The block splits fifteen minutes of teaching and thirty hands-on.

Warn them now that this is the block most likely to produce zero rows on the first attempt, and
that zero rows is almost never a code problem.
""")

    # ---------------------------------------------------------------- 7
    s = cards_slide(
        prs, "STAC in four nouns",
        [
            ("book", "Catalog",
             "The top of the tree. Planetary Computer publishes one, at "
             "/api/stac/v1. Everything else hangs off it."),
            ("layers", "Collection",
             "A dataset. `sentinel-2-l2a` is one. It carries the extent, the licence and the "
             "band definitions."),
            ("table", "Item",
             "One scene, at one time, over one footprint. This is the row you search for and the "
             "thing you record in bronze."),
            ("download", "Asset",
             "One file on an Item. B04 is an asset, SCL is an asset. Each is a Cloud Optimized "
             "GeoTIFF with an href."),
        ],
        kicker="Step 1", icon="satellite", accent=BRONZE, page=page(), total=TOTAL, columns=4,
        subtitle="Learn these four and every STAC API in the world is navigable.",
    )
    notes(s, """
The reason to teach the nouns rather than the API is that STAC is a standard, not a Microsoft
thing. Element 84, USGS, NASA and Planetary Computer all speak it. Learn it once.

If someone asks why not just use the Sentinel Hub API or a download portal: because those are
products, and this is a protocol. Your pipeline outlives the product.
""")

    # ---------------------------------------------------------------- 8
    s = compare_slide(
        prs, "Why a catalogue, not a file share",
        "What a STAC search gives you",
        ["Query by geometry, so you ask for your licence block, not a tile grid",
         "Query by date range and by cloud cover in the same call",
         "Metadata before download: projection, platform, processing baseline",
         "Signed hrefs to exactly the assets you asked for",
         "The same query works next month, and next year"],
        "What a file share costs you",
        ["Someone has to decide in advance which tiles to keep",
         "Cloud cover is discovered after the download, not before",
         "Provenance lives in a filename, and filenames drift",
         "Storage grows with everything you might need, not what you used",
         "The query is a person, and that person goes on leave"],
        kicker="Step 1", icon="search", page=page(), total=TOTAL,
        left_accent=GREEN, right_accent=RED,
        footnote="The last line on each side is the one that matters in three years.",
    )
    notes(s, """
Spend the time on the right-hand column. Most rooms have lived the file share version and will
recognise it immediately, which is what makes the catalogue argument land.

"The query is a person" is the line to say out loud. Every organisation has a folder that only
one person understands, and that is a single point of failure nobody has written down.
""")

    # ---------------------------------------------------------------- 9
    s = bullets_slide(
        prs, "Signing, and the mistake everyone makes once",
        [
            "Planetary Computer assets are in public blob storage but require a token appended to the URL",
            "`planetary_computer.sign_inplace` as a STAC modifier signs each item as it is read",
            "Tokens expire, typically within the hour, and an expired token gives you a 403 that reads like a permissions problem",
            "Sign late and never persist a signed href, because a signed URL written to a table is a credential in a table",
            "Bronze stores the href with the query string stripped, which is why notebook 01 splits on the question mark",
        ],
        kicker="Step 1", icon="key", accent=BRONZE, page=page(), total=TOTAL,
        footnote="If a scene loaded this morning and 403s this afternoon, you cached a signed URL somewhere.",
    )
    notes(s, """
This is the single most common support question in the block, and the failure is delayed: it
works in the session where you signed, and breaks in the scheduled run tomorrow.

Make the credential point explicitly. A signed href in a Delta table is a secret in a table that
gets backed up, replicated and read by anyone with access to the lakehouse. Strip it.
""")

    # ---------------------------------------------------------------- 10
    s = flow_slide(
        prs, "Cloud Optimized GeoTIFF, and why the window is cheap",
        [
            ("cloud", "Scene on blob", "A full Sentinel-2 tile is over a gigabyte across all bands.", BRONZE),
            ("table", "Internal tiling", "A COG is tiled and has overviews, with a header that maps tile to byte range.", BLUE),
            ("filter", "Range request", "The client reads the header, works out which tiles it needs, and asks for those bytes.", GREEN),
            ("check", "Your window", "A licence block at 20 m is a few megabytes, fetched in seconds.", GOLD),
        ],
        kicker="Step 1", icon="download", accent=BRONZE, page=page(), total=TOTAL,
        footnote="Passing bbox into odc.stac.load is what triggers this. Without it you download the tile.",
    )
    notes(s, """
This is the slide that explains why the hands-on finishes in thirty minutes rather than not at all.

The practical instruction: always pass bbox, and always pass resolution. Loading at 20 metres
rather than 10 costs nothing at stand scale and cuts the bytes by four. A twelve hectare stand is
about three hundred pixels at 20 m, which is more than enough for a stable median.
""")

    # ---------------------------------------------------------------- 11
    s = table_slide(
        prs, "The five bands, and what each is for",
        ["Asset", "Wavelength", "Res", "Used for"],
        [
            ["B04", "Red, 665 nm", "10 m", "NDVI and EVI, the greenness denominator"],
            ["B08", "Near infrared, 842 nm", "10 m", "Every index. Vegetation structure and biomass"],
            ["B11", "Shortwave infrared, 1610 nm", "20 m", "NDMI. Canopy moisture and drought stress"],
            ["B12", "Shortwave infrared, 2190 nm", "20 m", "NBR. Harvest and burn detection"],
            ["SCL", "Scene classification", "20 m", "Cloud, shadow and snow masking. Not optional"],
        ],
        widths=[0.8, 2.2, 0.7, 4.4],
        kicker="Step 1", icon="layers", accent=BRONZE, page=page(), total=TOTAL,
        footnote="Load all five in bronze. Deciding you do not need B12 is a silver decision, not a bronze one.",
    )
    notes(s, """
Foresters in the room will know the physics better than you do. Let them. Ask whether NDMI or
NBR matches what they use in the field and you will get a better answer than the slide.

The footnote is the layer discipline again. Dropping a band at ingest is a decision, and bronze
does not make decisions.
""")

    # ---------------------------------------------------------------- 12
    s = code_slide(
        prs, "The search, and the three filters",
        '''
catalog = pystac_client.Client.open(
    "https://planetarycomputer.microsoft.com/api/stac/v1",
    modifier=pc.sign_inplace,          # sign as items are read, never persist
)

search = catalog.search(
    collections=["sentinel-2-l2a"],
    bbox=[-66.90, 46.10, -66.40, 46.40],   # west, south, east, north
    datetime="2026-06-01/2026-08-31",
    query={"eo:cloud_cover": {"lt": 20}},
)

items = sorted(search.items(),
               key=lambda i: i.properties.get("eo:cloud_cover", 100))[:6]
''',
        caption="eo:cloud_cover is scene-wide. A scene can be 40 percent cloudy overall and perfectly "
                "clear over your block, so set a generous threshold and rank rather than filtering hard.",
        kicker="Step 1", icon="code", accent=BRONZE, page=page(), total=TOTAL,
    )
    notes(s, """
Walk the bbox order out loud: west, south, east, north. Then say that New Brunswick longitudes are
negative, around minus sixty-six. Both of those are in the troubleshooting list because both cost
somebody an hour in a previous delivery.

The ranking pattern is the useful habit. Filter generously, sort by quality, take the best few.
That way an unusually cloudy month degrades instead of returning nothing.
""")

    # ---------------------------------------------------------------- 13
    s = bullets_slide(
        prs, "Zero scenes: work the list in this order",
        [
            "Bounding box order. It is west, south, east, north, and a reversed box returns nothing without erroring",
            "Longitude sign. Positive 66 is Mongolia. New Brunswick is negative 66",
            "Date range. Widen it before you touch anything else, because a single month can genuinely be empty",
            "Cloud threshold. Raise it to 60 and rely on the ranking rather than the filter",
            "Only then suspect the collection name or the network",
        ],
        kicker="Step 1", icon="warning", accent=AMBER, page=page(), total=TOTAL,
        footnote="Notebook 01 prints exactly this list when the search returns nothing, so nobody has to remember it.",
    )
    notes(s, """
Put this on screen before the hands-on starts, not after, because it turns the most common thirty
minute stall into a two minute check.

The general lesson is worth naming: a query that returns nothing is not an error, so it will not
raise. Silent emptiness is the most expensive failure mode in data work, and the defence is to
validate the shape of what came back, not just that the call succeeded.
""")

    # ---------------------------------------------------------------- 14
    s = steps_slide(
        prs, "Hands-on 1: land the imagery",
        [
            ("Open the catalogue and search", "sentinel-2-l2a over your area of interest, your date window, cloud under 20.", "8 min"),
            ("Inspect one item before loading", "Read the projection, the platform and the asset list. Every number you publish traces back here.", "4 min"),
            ("Windowed load with odc.stac", "bands, bbox, resolution 20, chunks empty, groupby solar_day. No crs argument.", "8 min"),
            ("Write the scene catalogue", "One row per scene, hrefs unsigned, tagged with pipeline_run_id, appended not overwritten.", "6 min"),
            ("Persist the raw window", "COGs to Files/bronze/scenes/, then the session cache so notebook 02 does not re-download.", "4 min"),
        ],
        kicker="0:30  ·  30 min", icon="notebook", accent=BRONZE, page=page(), total=TOTAL,
    )
    notes(s, """
Circulate during step three. The no-crs-argument instruction is the one people override because
they think they are being helpful, and reprojecting in bronze breaks the layer contract in a way
that does not show up until silver produces subtly wrong areas.

Checkpoint: bronze_scene_catalog has at least two scenes, no signed hrefs, and the raster files
exist on disk.
""")

    # ---------------------------------------------------------------- 15
    s = section_slide(prs, 2, "Analyse it",
                      "Cloud masking, spectral indices, reprojection, and Copilot writing most of the code",
                      icon="filter", accent=SILVER, duration="50 min")
    notes(s, """
Notebooks 02 and 03. Twelve minutes of teaching, thirty-eight hands-on, and the hands-on is where
Copilot does the typing.

This is the block where the room's spectral knowledge is ahead of yours. Use it.
""")

    # ---------------------------------------------------------------- 16
    s = table_slide(
        prs, "The SCL classes, and which ones to drop",
        ["Value", "Class", "Keep?", "Why"],
        [
            ["3", "Cloud shadow", "Drop", "Depresses every band. Reads as dense wet canopy"],
            ["8", "Cloud medium probability", "Drop", "Partial obscuration, unpredictable direction"],
            ["9", "Cloud high probability", "Drop", "Opaque. Nothing below it is measurable"],
            ["10", "Thin cirrus", "Drop", "The dangerous one. Looks clear, depresses NDMI"],
            ["11", "Snow or ice", "Drop", "High reflectance across the board, inverts indices"],
            ["4, 5", "Vegetation, bare soil", "Keep", "This is the signal you came for"],
        ],
        widths=[0.7, 2.6, 0.9, 4.6],
        kicker="Step 2", icon="filter", accent=SILVER, page=page(), total=TOTAL,
        footnote="Thin cirrus is the one to dwell on: it survives a visual check and reads downstream as drought stress.",
    )
    notes(s, """
Spend the time on class 10. Cloud and shadow are obvious in a picture and get caught. Thin cirrus
does not, and it moves NDMI in the same direction that moisture stress does, so it produces a
plausible wrong answer rather than an obviously wrong one.

That is the pattern to name: the errors that hurt are the ones that look like findings.
""")

    # ---------------------------------------------------------------- 17
    s = cards_slide(
        prs, "Three indices, three questions",
        [
            ("tree", "NDVI  ·  greenness",
             "(B08 - B04) / (B08 + B04). Vigour and canopy density. Saturates over dense conifer, "
             "so it separates forest from not-forest better than it separates forest types."),
            ("cloud", "NDMI  ·  moisture",
             "(B08 - B11) / (B08 + B11). Canopy water content. The drought stress signal, and the "
             "one thin cirrus quietly corrupts."),
            ("warning", "NBR  ·  disturbance",
             "(B08 - B12) / (B08 + B12). Drops sharply after harvest or fire. Differenced between "
             "two dates it is the change detector."),
        ],
        kicker="Step 2", icon="chart", accent=SILVER, page=page(), total=TOTAL, columns=3,
        subtitle="All three are normalised ratios, which is why they survive illumination differences between dates.",
    )
    notes(s, """
The subtitle carries the important idea. A ratio cancels multiplicative effects, which is why you
can compare June to August without correcting for sun angle. That is also why the missing scale
factor in the next slide does not break NDVI: it cancels.

Ask the foresters which of these they would trust for a harvest check. You will usually get NBR
plus a caveat about partial cuts, which is exactly right.
""")

    # ---------------------------------------------------------------- 18
    s = bullets_slide(
        prs, "Reprojection: once, in silver, and only once",
        [
            "Sentinel-2 arrives in UTM, and central New Brunswick straddles zone 19 and zone 20",
            "A block spanning two zones gives you two different native CRSs in one search result",
            "Everything downstream reprojects to EPSG:2953, NAD83(CSRS) New Brunswick Stereographic, in metres",
            "Metres matter: area in degrees is meaningless, and a hectare figure computed in EPSG:4326 is wrong by a factor that varies with latitude",
            "Reproject the raster once in silver rather than reprojecting geometry per query, because per-query reprojection is both slower and inconsistently applied",
        ],
        kicker="Step 2", icon="globe", accent=SILVER, page=page(), total=TOTAL,
        footnote="Notebook 01 prints the native EPSG of every scene. If more than one appears, say so out loud.",
    )
    notes(s, """
The area point is the one that gets a reaction. Computing hectares in degrees produces a number
that looks like a number, goes into a report, and is wrong. Nothing errors.

If the room has GIS people they will already know this. Let them say it, because it lands better
from a peer than from the front.
""")

    # ---------------------------------------------------------------- 19
    s = flow_slide(
        prs, "From pixels to rows, which is where it becomes joinable",
        [
            ("satellite", "Raster stack", "Bands and indices on a 20 m grid, one layer per date.", SILVER),
            ("map", "Stand polygons", "The register, reprojected to the same CRS. Geometry must match or the join is silent nonsense.", BLUE),
            ("filter", "Zonal statistics", "Per stand, per date: median, mean and a valid pixel count.", GREEN),
            ("table", "One row per stand per date", "Now it joins to inventory, to operations, to anything Woodlands holds.", GOLD),
        ],
        kicker="Step 2", icon="pipeline", accent=SILVER, page=page(), total=TOTAL,
        footnote="Keep the valid pixel count. A stand median from four unmasked pixels is not the same fact as one from four hundred.",
    )
    notes(s, """
The footnote is the professional habit worth teaching. Every aggregate should carry the count it
was computed from, because otherwise a heavily clouded stand and a clear one look identical in the
output and only one of them is trustworthy.

Median rather than mean, because a single unmasked cloud edge pixel drags a mean and barely moves
a median.
""")

    # ---------------------------------------------------------------- 20
    s = code_slide(
        prs, "Prompt Copilot with intent and constraints, not syntax",
        '''
# Weak prompt: you get plausible code and inherit every assumption silently.
"write code to calculate NDVI"

# Strong prompt: states the input, the constraint, and what must not be assumed.
"""
Given an xarray Dataset with Sentinel-2 L2A bands B04, B08, B11, B12
and the SCL band:
  - mask cloud, shadow, snow and thin cirrus using SCL
  - return NDVI, NDMI and NBR as a single Dataset
  - the input is NOT reprojected and NOT scaled
  - masked pixels must become NaN, not zero
"""
''',
        caption="Then read what comes back and ask one question: what did it assume that I did not tell it?",
        kicker="Step 2", icon="copilot", accent=BLUE, page=page(), total=TOTAL,
    )
    notes(s, """
Demonstrate both prompts live if the room is warm. The weak one produces code that runs, which is
exactly what makes it dangerous.

The caption is the transferable skill and it is worth writing on a whiteboard. Not "is this code
correct", which is hard, but "what did it assume", which is answerable by reading.
""")

    # ---------------------------------------------------------------- 21
    s = cards_slide(
        prs, "Three assumptions to catch in this exercise",
        [
            ("warning", "The scale factor",
             "L2A reflectance is stored as integers and needs dividing by 10000. Copilot often omits it. "
             "NDVI still looks right because the ratio cancels, so the bug hides, and then NDMI "
             "thresholds are silently in the wrong place."),
            ("warning", "Nodata handling",
             "Zero is a real reflectance value in deep shadow. Treating zero as nodata deletes valid "
             "dark pixels, which biases every stand median upward on the shaded side of a slope."),
            ("warning", "The SCL class list",
             "Getting the class numbers slightly wrong leaves thin cirrus in the data. Cirrus depresses "
             "NDMI, which reads downstream as drought stress in stands that are fine."),
        ],
        kicker="Step 2", icon="brain", accent=AMBER, page=page(), total=TOTAL, columns=3,
        subtitle="All three produce output that runs, looks reasonable, and is wrong in a direction you would not question.",
    )
    notes(s, """
This is the intellectual centre of the morning. Take the full five minutes.

The common thread: none of these three raise an exception, none produce an obviously silly number,
and all three move a result in a direction that a forester might plausibly believe. That is the
definition of an expensive bug.

Ask the room how they would catch each one. The answers are: check a known stand against a known
value, check the range of your indices against physical limits, and look at the picture.
""")

    # ---------------------------------------------------------------- 22
    s = steps_slide(
        prs, "Hands-on 2: mask, index, and aggregate to stands",
        [
            ("Reproject to EPSG:2953", "Raster and register both. Confirm both report the same EPSG before joining.", "7 min"),
            ("Mask from SCL", "Drop 3, 8, 9, 10, 11. Masked becomes NaN. Verify the masked fraction is plausible.", "8 min"),
            ("Compute the three indices", "Apply the scale factor first. Sanity check that every index sits between -1 and 1.", "8 min"),
            ("Zonal statistics per stand", "Median per stand per date, plus the valid pixel count.", "9 min"),
            ("Classify in gold", "Threshold on NDVI and NDMI into softwood, hardwood, mixedwood, with a confidence.", "6 min"),
        ],
        kicker="1:12  ·  38 min", icon="notebook", accent=SILVER, page=page(), total=TOTAL,
    )
    notes(s, """
The range check in step three is the cheapest bug detector in the whole day. Any normalised
difference index outside minus one to one means the arithmetic is wrong, full stop.

Checkpoint: silver_stand_observations has one row per stand per scene date, and
gold_stand_classification assigns a class to every stand with a confidence.
""")

    # ---------------------------------------------------------------- 23
    s = section_slide(prs, 3, "Add AI where it earns its place",
                      "And spend real time on where it is quietly wrong",
                      icon="brain", accent=GOLD, duration="45 min")
    notes(s, """
Notebook 04. Fifteen minutes teaching, thirty hands-on.

Set the tone in one sentence: this is the block where we are honest about AI, which means being
specific about both what it is good at and where it will embarrass you.
""")

    # ---------------------------------------------------------------- 24
    s = compare_slide(
        prs, "Where a language model earns its place here",
        "Earns it",
        ["Turning twelve numeric columns into a two-sentence note a planner reads in a tooltip",
         "Reconciling free-text field notes against the classified result and flagging disagreements",
         "Drafting the change narrative between two dates for a what-changed panel",
         "Summarising a hundred stand notes into the five themes worth a site visit"],
        "Does not",
        ["Deciding the class. A threshold is auditable, reproducible and free",
         "Computing anything. Ask a model for a mean and you get a plausible mean",
         "Anything a forester must defend in a regulatory conversation",
         "Filling a gap in the data, which it will do willingly and invisibly"],
        kicker="Step 3", icon="brain", page=page(), total=TOTAL,
        left_accent=GREEN, right_accent=RED,
        footnote="The dividing line: language in, language out is fine. Numbers in, numbers out is not.",
    )
    notes(s, """
The footnote is the rule of thumb to leave them with, and it holds up well outside this workshop.

On the right-hand column, the first item usually gets pushback: surely a model could classify from
the spectral values? It can, and it will be roughly right, and you will not be able to explain a
single stand to a regulator or reproduce last month's answer. A threshold on NDVI you can write on
one line and defend for a decade.
""")

    # ---------------------------------------------------------------- 25
    s = cards_slide(
        prs, "Where AI is quietly wrong: three live demonstrations",
        [
            ("warning", "It restates numbers you never gave it",
             "Ask for a stand summary including area. It will produce an area, confidently, either "
             "invented or rounded in a way that changes the meaning. Nothing flags it."),
            ("warning", "It is not reproducible",
             "Ask it to classify from index values with no threshold definition. Run it twice. The "
             "answers differ and neither is wrong in a way you can point at."),
            ("warning", "It fills gaps with opinion",
             "Give it a stand with a missing NDMI. It will interpolate a judgement rather than say "
             "the data is absent, which is the one thing you actually needed to know."),
        ],
        kicker="Step 3", icon="warning", accent=RED, page=page(), total=TOTAL, columns=3,
        subtitle="Run all three live. They work every time, and watching it happen lands harder than being told.",
    )
    notes(s, """
Do these live, in that order. They escalate nicely.

Demonstration three is the one that changes minds, because a missing measurement is a finding.
A stand with no NDMI this month might be under persistent cloud, which is itself operational
information, and the model erases it with a confident sentence.

Do not let this turn into an anti-AI session. The point is not that the tool is bad, it is that
this specific use is outside what it can be trusted with, and the next slide is the fix.
""")

    # ---------------------------------------------------------------- 26
    s = flow_slide(
        prs, "The mitigation pattern, which is the actual deliverable",
        [
            ("gate", "Constrain", "JSON schema on the response. The model chooses words, never fields.", GOLD),
            ("shield", "Pre-compute", "Every number is calculated in Spark and passed in. The prompt forbids new numbers.", GREEN),
            ("check", "Validate", "Parse the response and check each number against the source row it came from.", BLUE),
            ("flag", "Record", "Write the narrative and a validation_status. Failures are suppressed, never dropped silently.", AMBER),
        ],
        kicker="Step 3", icon="shield", accent=GOLD, page=page(), total=TOTAL,
        footnote="A row that fails validation still appears, with the narrative withheld. Silence about a failure is worse than the failure.",
    )
    notes(s, """
This is what they take back to work. The pattern is not specific to forestry or to Foundry.

Dwell on the last box. The tempting implementation drops rows that fail validation, and then the
report looks clean while quietly losing stands. Keeping the row and suppressing the narrative
means somebody can see that fifteen stands failed and ask why.
""")

    # ---------------------------------------------------------------- 27
    s = code_slide(
        prs, "Schema-constrained output and the numeric guard",
        '''
schema = {
    "type": "object",
    "properties": {
        "summary":   {"type": "string", "maxLength": 320},
        "concern":   {"type": "string", "enum": ["none", "moisture", "disturbance"]},
        "confidence": {"type": "string", "enum": ["low", "medium", "high"]},
    },
    "required": ["summary", "concern", "confidence"],
    "additionalProperties": False,
}

# The guard: every number in the narrative must already exist in the source row.
emitted = set(re.findall(r"\\d+\\.?\\d*", response["summary"]))
allowed = {f"{row.area_ha:.1f}", f"{row.ndvi:.2f}", f"{row.ndmi:.2f}"}
status = "ok" if emitted <= allowed else "unverified_number"
''',
        caption="additionalProperties False stops invented fields. The regex guard stops invented numbers. "
                "Neither is clever, and that is the point.",
        kicker="Step 3", icon="code", accent=GOLD, page=page(), total=TOTAL,
    )
    notes(s, """
Walk the guard line by line. It is six lines of regex and set arithmetic, and it catches the
failure mode from demonstration one every time.

Say clearly that this is deliberately unsophisticated. A cleverer validator would be harder to
explain, harder to trust, and no better. Boring, auditable code is the right answer where the
output is going to a regulator.
""")

    # ---------------------------------------------------------------- 28
    s = steps_slide(
        prs, "Hands-on 3: enrich, then break it on purpose",
        [
            ("Build the prompt from a source row", "Pass only pre-computed values. Forbid new numbers explicitly in the system prompt.", "8 min"),
            ("Constrain the response", "JSON schema, additionalProperties false, enums on anything categorical.", "7 min"),
            ("Implement the numeric guard", "Extract every number from the narrative, compare against the source row, set validation_status.", "8 min"),
            ("Break the guard deliberately", "Remove it, re-run, and find the rows that now carry a number nobody computed.", "7 min"),
        ],
        kicker="2:20  ·  30 min", icon="notebook", accent=GOLD, page=page(), total=TOTAL,
    )
    notes(s, """
Step four is the one people remember. Removing a safeguard and watching bad data walk through is a
better teacher than any slide about why the safeguard exists.

Checkpoint: gold_stand_narrative exists, and at least one row carries a validation_status other
than ok, because the guard is doing its job. If everything is ok, the guard is probably not wired
in, and that is worth checking rather than celebrating.
""")

    # ---------------------------------------------------------------- 29
    s = section_slide(prs, 4, "Publish it",
                      "Star schema, Direct Lake, and a map a planner can actually filter",
                      icon="chart", accent=BLUE, duration="45 min")
    notes(s, """
Notebook 05 then the Power BI service. Twelve minutes teaching, thirty-three hands-on.

This is the block where the work becomes visible to somebody who does not write code, which is
the only reason any of it matters.
""")

    # ---------------------------------------------------------------- 30
    s = compare_slide(
        prs, "Direct Lake, against the two options it replaces",
        "Direct Lake",
        ["The semantic model reads the Delta parquet files directly",
         "No import, so no refresh window and no duplicated copy",
         "No per-visual round trip to a database engine",
         "New data is visible as soon as the Delta commit lands",
         "Memory-resident performance without an import schedule"],
        "Import and DirectQuery",
        ["Import: a second copy, a refresh window, and a staleness question",
         "Import: refresh duration grows with history, until it does not fit",
         "DirectQuery: a query per visual, at the mercy of source load",
         "DirectQuery: interactivity dies as concurrency rises",
         "Both: someone must own a refresh schedule forever"],
        kicker="Step 4", icon="delta", page=page(), total=TOTAL,
        left_accent=GREEN, right_accent=COPPER,
        footnote="Direct Lake falls back to DirectQuery silently. Knowing the triggers is the whole skill.",
    )
    notes(s, """
The footnote is the bit to slow down on, and it leads straight into the next slide.

The failure mode is that everything works in testing with a small model, then falls back in
production under real volume, and the only symptom is that the report got slow. Nobody gets an
error. Somebody gets a complaint three weeks later.
""")

    # ---------------------------------------------------------------- 31
    s = table_slide(
        prs, "What causes a silent fallback to DirectQuery",
        ["Trigger", "Why it happens", "What to do instead"],
        [
            ["Calculated columns", "Evaluated per row at model load, which Direct Lake cannot serve from parquet", "Compute the column in the gold notebook"],
            ["Complex DAX relationships", "Many-to-many and bidirectional filters force a query plan Direct Lake cannot satisfy", "Model a proper star with single-direction filters"],
            ["Views over the Delta table", "The SQL endpoint view is not the parquet file", "Point the model at the table itself"],
            ["Model exceeds the SKU guardrail", "Row and memory limits are per capacity SKU", "Aggregate in gold, or move up a SKU knowingly"],
            ["Unsupported data types", "A type the VertiPaq encoder will not take directly", "Cast in gold, not in the model"],
        ],
        widths=[2.0, 3.9, 3.1],
        kicker="Step 4", icon="warning", accent=AMBER, page=page(), total=TOTAL, size=11.5,
        footnote="Every fix is the same shape: do the work upstream in gold where it is testable, not in the model.",
    )
    notes(s, """
The footnote is the reusable principle. A calculated column in the semantic model is invisible to
your tests, your source control and your pipeline. The same logic in the gold notebook is all three.

Show them where to check: the Fabric capacity metrics app reports fallback, and the performance
analyzer in Desktop shows the query being pushed down. Checking it is a five minute habit that
saves a bad quarter.
""")

    # ---------------------------------------------------------------- 32
    s = cards_slide(
        prs, "Modelling gold for Direct Lake",
        [
            ("table", "gold_stand_facts",
             "One row per stand per period. Keys, the three index medians, the class, the valid pixel "
             "count. Narrow and long, never wide and sparse."),
            ("map", "gold_dim_stand",
             "One row per stand. Licence block, species group, area in hectares, and a latitude and "
             "longitude centroid alongside the WKB geometry."),
            ("calendar", "gold_dim_date",
             "A real date table with a contiguous range. Not derived at query time, not a column on "
             "the fact table. Time intelligence needs it."),
            ("layers", "gold_dim_class",
             "Softwood, hardwood, mixedwood, plus the threshold definition that produced each one, so "
             "the classification is self-documenting."),
        ],
        kicker="Step 4", icon="delta", accent=BLUE, page=page(), total=TOTAL, columns=4,
        subtitle="Four tables, single-direction relationships, no calculated columns anywhere.",
    )
    notes(s, """
The centroid point in dim_stand is practical and gets missed: the Power BI map visual wants points,
and the shape map wants a registered boundary set. Carrying a lat/long centroid alongside the WKB
means the common case works without anyone registering anything.

Storing the threshold definition in dim_class is a small thing that pays off in month four, when
somebody asks why a stand changed class and the answer is in the model rather than in a notebook
nobody can find.
""")

    # ---------------------------------------------------------------- 33
    s = steps_slide(
        prs, "Hands-on 4: publish and prove it",
        [
            ("Build the facts and dimensions", "Clean grain, real keys, no nulls in anything you will filter on.", "9 min"),
            ("Create the Direct Lake model", "From the Lakehouse. Set relationships single-direction. Mark the date table.", "8 min"),
            ("Add four measures", "Stand count, area by class, harvested area since last period, moisture stress flag.", "7 min"),
            ("Build the report page", "Map by class, trend by month, table with the AI narrative in the tooltip.", "6 min"),
            ("Prove Direct Lake is in use", "Check for fallback rather than assuming. This is the step everyone skips.", "3 min"),
        ],
        kicker="3:02  ·  33 min", icon="chart", accent=BLUE, page=page(), total=TOTAL,
    )
    notes(s, """
Step five takes three minutes and is the difference between a report that works today and one that
still works at scale. Do not let the room skip it because they are running late.

Checkpoint: a report page that answers the problem statement from 0:00. Put that slide back up and
check it literally, clause by clause.
""")

    # ---------------------------------------------------------------- 34
    s = cards_slide(
        prs, "Optional: the same gold layer as a Fabric App",
        [
            ("people", "Different audience",
             "The Power BI report serves anyone who wants to explore. The app serves one role with "
             "fixed questions and no exploration at all."),
            ("target", "Chief Forester view",
             "Five cards, a class breakdown, a review queue and a stand detail panel. Nothing else, "
             "on purpose."),
            ("check", "The teaching point",
             "A gold layer that can only feed one consumer is not really a gold layer. Same tables, "
             "second front end, no new pipeline."),
        ],
        kicker="Step 4, optional", icon="rocket", accent=GREEN, page=page(), total=TOTAL, columns=3,
        subtitle="Ten minute demo, or a twenty-five minute extension if Docker works everywhere and the workload is enabled.",
    )
    notes(s, """
Judge the room. If Step 4 ran long, demo this in ten minutes and point at the folder.

The teaching point in card three is the one that survives even as a pure demo, so make sure you
say it even if you show nothing: if your gold layer only works for the one report you happened to
build, you built a report, not a data product.
""")

    # ---------------------------------------------------------------- 35
    s = section_slide(prs, 5, "Make it repeatable",
                      "Because the requirement said nobody opens a notebook",
                      icon="pipeline", accent=GREEN, duration="25 min")
    notes(s, """
Put the problem statement back on screen for this. The phrase "without anyone opening a notebook"
is the entire justification for this block, and it is the difference between what we have built so
far and something Woodlands can actually rely on.
""")

    # ---------------------------------------------------------------- 36
    s = flow_slide(
        prs, "The pipeline, five activities and one gate",
        [
            ("download", "Bronze ingest", "Notebook 01, parameterised on area of interest and date window.", BRONZE),
            ("filter", "Silver derive", "Notebook 02. Mask, reproject, index, aggregate to stands.", SILVER),
            ("gate", "Quality gate", "Fail the run if scene count, masked fraction or stand coverage is out of bounds.", RED),
            ("brain", "Gold classify and enrich", "Notebooks 03 and 04. Threshold, then the validated narrative.", GOLD),
            ("chart", "Publish", "Notebook 05. Facts and dimensions land, Direct Lake picks them up.", BLUE),
        ],
        kicker="Step 5", icon="pipeline", accent=GREEN, page=page(), total=TOTAL,
        footnote="The gate is the only activity that exists to stop the pipeline. Everything else exists to move it forward.",
    )
    notes(s, """
The gate placement is deliberate and worth explaining: after silver, before gold. Late enough that
you can measure real data quality, early enough that a bad month never reaches anything a planner
sees.

Ask what the gate should check. You want scene count above zero, masked fraction below a
threshold, and stand coverage close to the register size. All three are cheap and all three catch a
different failure.
""")

    # ---------------------------------------------------------------- 37
    s = bullets_slide(
        prs, "Parameters, schedule, and what happens when it fails",
        [
            "Parameterise the area of interest and the date window, so the same pipeline serves every licence block",
            "Schedule monthly, a few days after month end, so the imagery has had time to land in the catalogue",
            "On failure, notify a person and leave the previous month's gold tables untouched",
            "Never publish a partial month. A gap is visible and recoverable, wrong numbers are neither",
            "Log the pipeline_run_id through every layer, so any published number traces back to the scenes behind it",
        ],
        kicker="Step 5", icon="calendar", accent=GREEN, page=page(), total=TOTAL,
        footnote="The run id is the thread that answers 'where did this number come from' six months later.",
    )
    notes(s, """
Bullet four is a judgement call worth arguing about with the room, and it usually splits them.
Publishing a partial month keeps the dashboard fresh and quietly degrades the trend. Failing loudly
looks worse on the day and is better every day after.

Come down on the side of failing loudly, but let them push back, because in some organisations the
dashboard going stale is a genuine operational problem.
""")

    # ---------------------------------------------------------------- 38
    s = table_slide(
        prs, "What actually breaks in production",
        ["Failure", "What you see", "Design for it now"],
        [
            ["No clear scene this month", "Empty result, no error", "Widen the window and rank, gate on scene count"],
            ["Area crosses a UTM zone", "Two native CRSs in one result", "Reproject in silver, never mosaic in bronze"],
            ["Stand IDs change in the register", "Orphaned facts, silent row loss", "Key on a stable id, gate on stand coverage"],
            ["Foundry deployment version moves", "Narrative style drifts, schema may break", "Pin the deployment, validate the schema every run"],
            ["A dependency updates underneath you", "Code unchanged, run fails", "Pin the library set in a published Environment"],
        ],
        widths=[2.6, 2.9, 3.5],
        kicker="Step 5", icon="warning", accent=AMBER, page=page(), total=TOTAL, size=11.5,
        footnote="Every row here has happened. The last one happened while building this workshop.",
    )
    notes(s, """
Tell the story behind the last row, because it is fresh and it is real.

Building this material, notebook 01 failed with a Spark session cancellation and no other detail.
Nothing in our code had changed. The cause was a transitive dependency, affine, releasing version
3.0.1, in which iterating a transform raises a TypeError. odc-geo unpacks transforms, so every
single raster load failed. The fix was one line: pin affine below 3.

Two lessons. First, that is why the library set is pinned in a published Environment rather than
installed ad hoc. Second, the platform error message named no cell and no exception, so the only
way to find it was to run the notebook cell by cell inside a harness that caught everything. When
a scheduled run gives you an unattributable failure, get the real traceback before forming a theory.
""")

    # ---------------------------------------------------------------- 39
    s = quote_slide(
        prs,
        "A notebook that works is a demonstration.\nA pipeline that runs when nobody is watching\nis a product.",
        "The difference is parameters, a schedule, a quality gate, and someone's name on the failure alert.",
        accent=GREEN, icon="rocket", page=page(), total=TOTAL,
    )
    notes(s, """
Pause here. This is the sentence the day has been building towards.

If anyone in the room takes one idea back to their team, this is the one worth taking, and it
applies well beyond forestry or Fabric.
""")

    # ---------------------------------------------------------------- 40
    s = bullets_slide(
        prs, "The assignment",
        [
            "Run the full pipeline over one of your own licence blocks, not the workshop area of interest",
            "Choose a date window with a genuine data problem in it and handle it, rather than picking a clean month",
            "Add one quality gate of your own design, and document what it protects against",
            "Publish a report page that answers a question your own team actually asks",
            "Write one paragraph on what you would not automate, and why",
        ],
        kicker="Assignment", icon="target", accent=GREEN, page=page(), total=TOTAL,
        footnote="Full brief in docs/08-assignment.md. Two weeks. Office hours weekly.",
    )
    notes(s, """
The last bullet is the one that separates a good submission from a competent one. Knowing where
automation stops being appropriate is a senior judgement, and asking for it in writing forces the
thinking.

Expect answers about final harvest sign-off, anything with a regulatory signature, and any
decision where a person is accountable for the outcome. All correct.
""")

    # ---------------------------------------------------------------- 41
    s = cards_slide(
        prs, "Where to get unstuck",
        [
            ("notebook", "Solution notebooks",
             "Complete, runnable answers for all six exercises in notebooks/solutions/. Reading one is "
             "the designed path, not a failure."),
            ("book", "Troubleshooting guide",
             "docs/09-troubleshooting.md, organised by symptom rather than by cause, because you know "
             "the symptom first."),
            ("gear", "Environment reference",
             "docs/12-spark-environment.md covers the pinned library set, why each pin exists, and how "
             "to rebuild it from scratch."),
            ("layers", "Workspace layout",
             "docs/13-three-workspace-layout.md explains the bronze, silver and gold split and the "
             "shortcuts that connect them."),
            ("people", "Office hours",
             "Weekly for the two weeks of the assignment. Bring the notebook, not a description of the "
             "notebook."),
            ("flag", "The channel",
             "Five minutes stuck is learning. Twenty is waste. Post the error and the cell."),
        ],
        kicker="Support", icon="compass", accent=GREEN, page=page(), total=TOTAL, columns=3,
    )
    notes(s, """
Say the office hours line properly: bring the actual notebook and the actual error. A description
of a problem takes twenty minutes to unpick and the notebook takes two.
""")

    # ---------------------------------------------------------------- 42
    s = bullets_slide(
        prs, "What you built today",
        [
            "A bronze layer that records what arrived, with the provenance to explain any number six months from now",
            "A silver layer that makes scenes comparable: one projection, cloud removed, one row per stand per date",
            "A gold layer that carries meaning: a classification you can defend and a narrative that cannot invent numbers",
            "A semantic model that reads Delta directly, and a report that answers the question we started with",
            "A scheduled pipeline with a quality gate, which is the part that makes the rest of it real",
        ],
        kicker="Wrap", icon="check", accent=GREEN, page=page(), total=TOTAL,
        footnote="Everything here is in the repo, runs end to end, and has been executed against a live capacity.",
    )
    notes(s, """
Read the last bullet slowly. Most of the room came in thinking the satellite imagery would be the
hard part. It was not. The hard parts were the projection, the layer discipline, and being honest
about AI.

The footnote matters for credibility: this is not a deck describing a hypothetical pipeline.
""")

    # ---------------------------------------------------------------- 43
    s = compare_slide(
        prs, "The two habits worth keeping",
        "Do this",
        ["Validate the shape of what came back, not just that the call succeeded",
         "Compute numbers where they can be tested, then pass them to the model",
         "Carry the count alongside every aggregate",
         "Pin the library set, and know why each pin exists",
         "Make the failure loud and the provenance traceable"],
        "Not this",
        ["Assuming an empty result is a bug in your code",
         "Asking a model for a number you could calculate",
         "Publishing a median without knowing what it came from",
         "Installing packages ad hoc and hoping the resolver is kind",
         "Letting a partial month look like a complete one"],
        kicker="Wrap", icon="lightbulb", page=page(), total=TOTAL,
        left_accent=GREEN, right_accent=RED,
        footnote="None of these are about satellites. They are how you keep any data product trustworthy.",
    )
    notes(s, """
This is the transferable content and it is the right note to end the teaching on.

If the room is engaged, ask which of the five on the right they have personally shipped. You will
get honest answers and it makes the list stick.
""")

    # ---------------------------------------------------------------- 44
    s = closing_slide(
        prs, "Questions, then office hours",
        [
            "Assignment brief: docs/08-assignment.md, two weeks, office hours weekly",
            "Everything runs: notebooks, pipeline, Power BI guide and the optional Fabric App are all in the repo",
            "Bring one real question about your own operating area to the first office hours",
            "The last ten minutes are open, and facilitators are circulating",
        ],
        "JDI Woodlands  ·  Automating forest classification on Microsoft Fabric  ·  Session 2 of 2",
        icon="rocket", accent=GREEN,
    )
    notes(s, """
Do not end on a thank you slide with nothing on it. End on the assignment, because that is what
happens next.

Then stop talking and circulate. The best conversations of the whole workshop happen in these ten
minutes, one to one, and they do not happen if you are still at the front.
""")

    return prs


if __name__ == "__main__":
    deck = build()
    assert len(deck.slides) == TOTAL, (
        f"slide count drifted: built {len(deck.slides)}, expected {TOTAL}. "
        "Update TOTAL or fix the page() calls."
    )
    out = save(deck, "session-2-build-it-end-to-end.pptx")
    summarise(deck, out)
