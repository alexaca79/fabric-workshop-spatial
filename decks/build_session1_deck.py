"""Build the Session 1 deck: environment and data foundations.

Run from the repository root::

    python decks/build_session1_deck.py

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

TOTAL = 41
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
        "Automating forest classification\non Microsoft Fabric",
        "Session 1  ·  Environment and data foundations",
        "JDI Woodlands  ·  Four hours  ·  From an empty workspace to a Delta table you could query today",
        "Session 1 of 2  ·  Bring a laptop, a workspace, and one real question about your own data",
        icon_row=["satellite", "layers", "lakehouse", "notebook", "chart", "forest"],
    )
    notes(s, """
Welcome. Two sessions, four hours each. By the end of Session 2 everyone in this room will
have a scheduled pipeline that pulls satellite imagery, classifies forest stands, and drives
a map a planner can filter.

Today is the foundations. That sounds like the boring half. It is not, because almost every
failure in the second session traces back to something we get right or wrong this morning:
the projection, the layer contracts, and knowing which tool to reach for.

Housekeeping before we start: we run the pre-flight check first, before introductions. If your
environment is broken I want to know at nine o'clock, not at half past eleven.
""")

    # ---------------------------------------------------------------- 2
    s = bullets_slide(
        prs, "What you leave with today",
        [
            "A Fabric workspace and a Lakehouse that you built, not one that was handed to you",
            "A Woodlands stand register landed as a Delta table, reprojected to the New Brunswick grid",
            "A decision rule for picking a tool chain that you can apply without asking anyone",
            "A working understanding of why bronze, silver and gold exist, rather than that they do",
            "One homework task that puts your own operating area into the pipeline",
        ],
        kicker="Session 1", icon="target", page=page(), total=TOTAL,
        footnote="If you leave with only one thing, make it the layer contracts. Everything else is tooling.",
    )
    notes(s, """
Read these out and then say the honest version: the tooling changes. Fabric will look different
in eighteen months. The layer contracts will not, and neither will the projection problem.

The last bullet matters more than it looks. The homework is what turns this from a demo you
watched into a pipeline over ground you know.
""")

    # ---------------------------------------------------------------- 3
    s = table_slide(
        prs, "Running order",
        ["Time", "Block", "Min"],
        [
            ["0:00", "Pre-flight, environment and access check, with a fallback for anyone blocked", "20"],
            ["0:20", "Owning an analytics product, what we are and are not building", "20"],
            ["0:40", "Your environment tool by tool", "45"],
            ["1:25", "Choosing a tool chain, three problem patterns and how to pick", "30"],
            ["1:55", "Break", "15"],
            ["2:10", "Fabric and OneLake, workspaces, Lakehouse, shortcuts, SQL endpoint", "40"],
            ["2:50", "Hands-on, land a dataset, reproject it, write a Delta table", "50"],
            ["3:40", "Wrap and homework brief", "20"],
        ],
        widths=[0.9, 6.5, 0.7],
        kicker="Agenda", icon="clock", page=page(), total=TOTAL,
        footnote="Two checkpoints, at 1:25 and 3:25. Nobody carries a broken environment past a checkpoint.",
    )
    notes(s, """
Point at the two hands-on blocks and say that everything before them is there to make them work.

Flag the break time now so people plan around it. A room that does not know when the break is
takes its own break, one person at a time, during the block you most needed them for.
""")

    # ---------------------------------------------------------------- 4
    s = cards_slide(
        prs, "How today works",
        [
            ("checklist", "Checkpoints",
             "Two of them. At each one you run a validation cell that prints PASS or FAIL per assertion. "
             "Green means carry on."),
            ("notebook", "Solution notebooks",
             "Every exercise has a complete answer key. Using it at a checkpoint is the designed path, "
             "not giving up."),
            ("people", "Fallback tiers",
             "Shared workspace, then pairing, then read-only. Three ways to keep going, none of them "
             "a failure state."),
            ("flag", "Ask early",
             "Five minutes stuck is learning. Twenty is waste. Put it in the Teams channel and someone "
             "answers."),
            ("target", "One real question",
             "Bring a question about your own data. The last block of Session 2 is where it connects."),
            ("clock", "We run to time",
             "The hands-on blocks absorb overrun from everything before them, so the tour ends when "
             "the timer says."),
        ],
        kicker="Ground rules", icon="compass", page=page(), total=TOTAL, columns=3,
    )
    notes(s, """
Spend a full minute on the solution notebooks. In every delivery there is someone who will sit
quietly with a broken cell for forty minutes rather than open the answer, and they learn less
than the person who read the answer at minute six and then re-typed it themselves.

Say the sentence out loud: reading a working answer is not the same as having written one, so
open it, read it, close it, and write your own.
""")

    # ---------------------------------------------------------------- 5
    s = section_slide(prs, 1, "Pre-flight", "Find broken environments while there is still time to fix them",
                      icon="checklist", accent=AMBER, duration="0:00  ·  20 min")
    notes(s, """
No introductions yet. Everyone opens the notebook and runs the pre-flight cell now.

Floating facilitator: walk the room and look at screens rather than waiting for hands. People
do not raise their hand for a failure they think is their own fault.
""")

    # ---------------------------------------------------------------- 6
    s = cards_slide(
        prs, "What the pre-flight checks",
        [
            ("code", "Python and Spark", "The session starts, and it starts in under a couple of minutes."),
            ("lakehouse", "Lakehouse attached", "lh_woodlands is the default. Nothing works without this."),
            ("delta", "Delta write and read", "A real write and a real read, then a clean-up. Permissions are proved, not assumed."),
            ("cloud", "Outbound DNS", "The Spark session can resolve planetarycomputer.microsoft.com."),
            ("satellite", "STAC API reachable", "A live call to the Sentinel-2 collection endpoint."),
            ("brain", "Foundry endpoint", "Expected to be missing today. Notebook 04 has an offline path."),
        ],
        kicker="Block 1", icon="checklist", accent=AMBER, page=page(), total=TOTAL, columns=3,
        subtitle="Standard library only, so it runs before any pip install has happened",
    )
    notes(s, """
The script deliberately has no dependencies. If it needed geopandas to tell you geopandas was
missing, it would be useless.

Note the last card out loud. Foundry failing today is expected and not a problem. Say it now,
or three people will spend the break trying to fix it.
""")

    # ---------------------------------------------------------------- 7
    s = table_slide(
        prs, "Triage: symptom, cause, fix",
        ["Symptom", "Cause", "Fix"],
        [
            ["No default lakehouse", "Notebook opened outside the Lakehouse context",
             "Explorer pane, add lh_woodlands, set default, restart session"],
            ["Delta write denied", "Workspace on a Pro licence, or you have Viewer role",
             "Move to the shared capacity workspace"],
            ["DNS resolution fails", "Tenant blocks outbound traffic from Spark",
             "Cached-scene fallback, staged in the shared workspace"],
            ["STAC ok, assets 403", "Signing step skipped", "Every href must pass through planetary_computer.sign"],
            ["Import errors", "Environment not attached", "Run the pip cell, or attach env-woodlands-geo"],
            ["Session start over 5 min", "Capacity cold or throttled", "Tell a facilitator, do not retry"],
        ],
        widths=[1.5, 2.4, 3.4],
        kicker="Block 1", icon="warning", accent=AMBER, page=page(), total=TOTAL, size=11.5,
    )
    notes(s, """
Do not read this table aloud. Leave it up while you walk the room, and point at the row that
matches whatever a person is looking at.

The last row is the one facilitators get wrong. A throttled capacity does not improve by being
asked again, and three people hammering restart makes it worse for everyone else.
""")

    # ---------------------------------------------------------------- 8
    s = steps_slide(
        prs, "If you are still blocked, in this order",
        [
            ("Shared workspace", "ws-woodlands-shared, write access, every solution notebook already run. "
                                 "You work there and lose nothing.", "Tier 1"),
            ("Pair up", "Two people, one keyboard, and the person who is blocked drives. "
                        "This is the best of the three and nobody ever picks it first.", "Tier 2"),
            ("Read-only", "Work locally against the committed sample outputs and rejoin at the next break.", "Tier 3"),
        ],
        kicker="Block 1", icon="handoff", accent=AMBER, page=page(), total=TOTAL,
    )
    notes(s, """
Say clearly that none of these is a failure state. The point of the day is the pattern, and the
plumbing is the part most likely to be different at your site anyway.

Push tier 2 harder than feels natural. Pairing produces the best outcome and the lowest uptake,
because being the one who is stuck feels like a confession.
""")

    # ---------------------------------------------------------------- 9
    s = section_slide(prs, 2, "Owning an analytics product",
                      "What separates a pipeline someone maintains from a notebook someone once ran",
                      icon="people", duration="0:20  ·  20 min")
    notes(s, """
Shift gear here. The pre-flight was mechanical; this block is the framing that everything else
hangs on. Slow down, and get people talking.
""")

    # ---------------------------------------------------------------- 10
    s = compare_slide(
        prs, "A notebook that ran, and a product someone owns",
        "Product", [
            "Has a named user making a named decision",
            "Refreshes on a schedule nobody has to remember",
            "Fails loudly, in a way that reaches a human",
            "Every number traces back to a source without a re-run",
            "A second person has changed it without asking the author",
        ],
        "Notebook", [
            "Has an author, and the author is the interface",
            "Refreshes when someone remembers to open it",
            "Fails silently, or produces a plausible wrong answer",
            "Numbers are reproducible only by re-running everything",
            "Exactly one person can safely change it",
        ],
        kicker="Block 2", icon="people", page=page(), total=TOTAL,
        left_accent=GREEN, right_accent=COPPER,
        footnote="An analytics product with exactly one person who can run it is a risk with a dashboard attached.",
    )
    notes(s, """
The right column is not a criticism. Every product starts as that notebook, and most analysis
should stay there. The mistake is letting something reach an operational decision while still
having the properties in the right column.

Ask the room which column their current work sits in. There is usually a long pause and then
an honest answer, and that answer is the most useful thing said all morning.
""")

    # ---------------------------------------------------------------- 11
    s = cards_slide(
        prs, "Before you write a line of code, answer these",
        [
            ("people", "Who is the user",
             "A Woodlands planner deciding where to send a crew next season. Not a data scientist, "
             "and not a dashboard."),
            ("target", "What decision changes",
             "Which stands get visited, and in what order. If no decision changes, you are building "
             "a screensaver."),
            ("calendar", "How often it refreshes",
             "Monthly. That single answer determines the imagery cadence, the compute cost and the "
             "whole architecture."),
            ("check", "What done looks like",
             "A number on a map, with a date attached, that a forester will act on without ringing "
             "you first."),
            ("warning", "What it must never do",
             "Make a silvicultural decision on its own, or produce a number nobody can trace."),
            ("shield", "Who defends it",
             "Whoever is in the room when a regulator asks. Design for that conversation now."),
        ],
        kicker="Block 2", icon="target", page=page(), total=TOTAL, columns=3,
    )
    notes(s, """
Run this as a conversation, not a slide. Ask the room for their answer to card one before you
give yours.

If there is a planner in the room, hand them card two entirely. The abstraction only lands when
it is attached to a real person making a real decision, and their answer will be more specific
than anything on this slide.
""")

    # ---------------------------------------------------------------- 12
    s = bullets_slide(
        prs, "What we are not building today",
        [
            "A research-grade classifier. Published accuracy figures need labelled ground truth we do not have",
            "A replacement for field cruising. This narrows where a crew goes; it does not tell you what is there",
            "Anything that detects change below a 20 metre pixel, so selective thinning stays invisible",
            "A system that makes a decision. Every output lands in front of a person who decides",
            "A permanent answer. Thresholds get argued with, and the argument is the point",
        ],
        kicker="Block 2", icon="warning", accent=COPPER, page=page(), total=TOTAL,
        footnote="Being explicit about the limits is what makes the claims that remain defensible.",
    )
    notes(s, """
This slide buys credibility. A room of foresters has seen remote sensing oversold before, and
saying the limits out loud before anyone asks changes how the rest of the day is heard.

The fourth bullet is the important one. Everything we build ends in a work queue, not an
instruction.
""")

    # ---------------------------------------------------------------- 13
    s = medallion_slide(
        prs, "The three contracts",
        ["Fidelity to what arrived", "Append only, never overwritten", "No reprojection, no masking, no renaming",
         "Stores unsigned URLs, never a credential"],
        ["Comparability across scenes and dates", "Cloud masked, reflectance scaled, reprojected once",
         "Indices computed, pixel accounting carried", "No business rules and no thresholds"],
        ["Meaning for a named decision", "Classification, change detection, narrative",
         "Every number traces to a silver row", "Star schema, ready for Direct Lake"],
        kicker="Block 2", page=page(), total=TOTAL,
        footnote="The test: if a number is questioned, you can walk it back to a bronze row without re-running anything.",
    )
    notes(s, """
This is the slide to come back to all day. Every time someone proposes putting something
somewhere, the question is which contract it belongs under.

The most common violation is reprojecting in bronze because it is convenient. It is convenient
right up to the month someone asks what the original grid was.
""")

    # ---------------------------------------------------------------- 14
    s = section_slide(prs, 3, "Your environment, tool by tool",
                      "Five tools, one live action each. Nobody watches a slide about a product they have not touched",
                      icon="gear", accent=BLUE, duration="0:40  ·  45 min")
    notes(s, """
Hard timer per tool. This block overruns in every delivery because people want to explore, and
the exploration is better done in the break when it does not cost the room forty minutes.
""")

    # ---------------------------------------------------------------- 15
    s = table_slide(
        prs, "Five tools, five live actions",
        ["Tool", "Time", "What you do, right now"],
        [
            ["Microsoft Fabric", "12 min", "Create a workspace, create lh_woodlands, look at Files and Tables"],
            ["Power BI", "8 min", "Open the SQL analytics endpoint, run one SELECT, see the same data"],
            ["Planetary Computer", "10 min", "Search Sentinel-2 for your area, read one STAC item properly"],
            ["GitHub Copilot", "10 min", "Ask for a reprojection snippet, then find the mistake in the answer"],
            ["Microsoft Foundry", "5 min", "Open a project, find a deployed model, note the endpoint and version"],
        ],
        widths=[1.6, 0.8, 4.6],
        kicker="Block 3", icon="gear", accent=BLUE, page=page(), total=TOTAL,
        footnote="The Copilot segment is deliberately adversarial. You are looking for the bug, not the answer.",
    )
    notes(s, """
Announce the timer and mean it. When the timer goes, move, even mid-sentence, and tell the room
that is what you are doing so it reads as discipline rather than rudeness.
""")

    # ---------------------------------------------------------------- 16
    s = bullets_slide(
        prs, "Microsoft Fabric",
        [
            "One SaaS surface over one storage account, so Spark, T-SQL and Power BI read the same bytes",
            "The workspace is the unit of access, capacity and lifecycle. Arguments about permissions are arguments about workspaces",
            "Capacity is what you are billed for, and throttling is a capacity event, not a workspace one",
            "Items live in a workspace: Lakehouse, Notebook, Pipeline, Semantic model, Report",
            "Your action: create ws-woodlands-yourname, create lh_woodlands, and open both Files and Tables",
        ],
        kicker="Block 3  ·  Tool 1", icon="lakehouse", accent=BLUE, page=page(), total=TOTAL,
    )
    notes(s, """
Do this live and slowly. Half the room has never created a workspace, and the ones who have
will tolerate ninety seconds of watching far better than the others will tolerate being lost.

If workspace creation is blocked by tenant policy, this is where you find out. Have the
pre-created workspaces ready.
""")

    # ---------------------------------------------------------------- 17
    s = bullets_slide(
        prs, "Power BI and the SQL analytics endpoint",
        [
            "Every Lakehouse ships with a read-only T-SQL endpoint over the same Delta files",
            "No copy, no load step, no second refresh schedule. A different engine on identical bytes",
            "This is the fastest way to sanity check a table you just wrote from a notebook",
            "Metadata sync is asynchronous, so a table can take a minute or two to appear",
            "Your action: open the endpoint, run one SELECT against a table, and notice you loaded nothing",
        ],
        kicker="Block 3  ·  Tool 2", icon="chart", accent=BLUE, page=page(), total=TOTAL,
        footnote="Mention the sync lag now. It looks like a bug at 3:10 and costs ten minutes of debugging.",
    )
    notes(s, """
The point that lands is "you loaded nothing". Most people in the room have spent years moving
data between a lake and a warehouse, and the idea that both engines read the same files is the
part worth pausing on.
""")

    # ---------------------------------------------------------------- 18
    s = bullets_slide(
        prs, "Planetary Computer and STAC",
        [
            "A catalogue of open Earth observation data, with Sentinel-2 Level 2A as our source",
            "STAC is the query standard: Catalog, then Collection, then Item, then Asset",
            "You search by geometry, date and property, and get back links to Cloud Optimized GeoTIFFs",
            "Assets need signing, and the signature expires, so you sign at the point of use",
            "Your action: open the Explorer, draw a box on your area, and read one item's properties",
        ],
        kicker="Block 3  ·  Tool 3", icon="satellite", accent=BLUE, page=page(), total=TOTAL,
    )
    notes(s, """
Have the Explorer open before this slide. Drawing the box live is what makes the bounding box
concept concrete, and it is the same box people will paste into their homework.

Point at the cloud cover slider and say that this one number is what breaks live demos, which
gives you cover if it breaks yours in Session 2.
""")

    # ---------------------------------------------------------------- 19
    s = bullets_slide(
        prs, "GitHub Copilot, used adversarially",
        [
            "It writes most of the code in Session 2, and that is a good outcome, not a compromise",
            "It optimises for a plausible answer to the question you asked",
            "Geospatial work is full of questions people ask imprecisely, which is where it goes wrong",
            "The skill being taught is reading the answer, not generating it",
            "Your action: ask it to reproject a GeoDataFrame to New Brunswick coordinates, then find the bug",
        ],
        kicker="Block 3  ·  Tool 4", icon="copilot", accent=BLUE, page=page(), total=TOTAL,
        footnote="Run the same prompt twice. The two answers differ, and that difference is the lesson.",
    )
    notes(s, """
Do not editorialise about AI here. Just run it, twice, and let the room see the variance.

The framing to land: it is not unreliable, it is under-specified. The next slide shows the same
prompt with the missing constraints added, and it gets it right.
""")

    # ---------------------------------------------------------------- 20
    s = code_slide(
        prs, "The same task, two prompts",
        """# Prompt A: "reproject this GeoDataFrame to New Brunswick coordinates"
gdf = gdf.to_crs("EPSG:2953")          # raises if gdf.crs is None
gdf["area"] = gdf.geometry.area        # what unit? nobody said

# Prompt B: "the frame is in WGS84 but has no CRS set. Declare it, reproject
#            to EPSG:2953, then compute area in hectares."
gdf = gdf.set_crs(4326)                # declare what it already is
gdf = gdf.to_crs(2953)                 # then transform
gdf["area_ha"] = gdf.geometry.area / 10_000""",
        caption="Same model, same session, thirty seconds apart. The difference is the constraints in the prompt, "
                "not the intelligence of the tool.",
        kicker="Block 3  ·  Tool 4", icon="copilot", accent=BLUE, page=page(), total=TOTAL,
    )
    notes(s, """
Walk the two blocks line by line. In prompt A, set_crs is missing, so it raises on naive
geometry, and if it does not raise, area is in square degrees.

Then make the general point: state the coordinate system, state the units, state the nodata
convention. Those three sentences fix most of the geospatial code an assistant will write for
you, and they are also the three things a colleague would have asked.
""")

    # ---------------------------------------------------------------- 21
    s = bullets_slide(
        prs, "Microsoft Foundry",
        [
            "Where the language model lives, as a named, versioned deployment behind an endpoint",
            "In this pipeline it does exactly one job: turning numbers into a sentence a planner reads",
            "It never classifies, never calculates, and never decides. Session 2 shows why",
            "The deployment name is recorded alongside every generated sentence, so wording changes are explainable",
            "Your action: find the project, find a deployment, and write down its name and version",
        ],
        kicker="Block 3  ·  Tool 5", icon="brain", accent=BLUE, page=page(), total=TOTAL,
        footnote="No Foundry access today? Everything still runs. Notebook 04 has an offline path that produces the same table.",
    )
    notes(s, """
Keep this short. It is five minutes and the substance is all in Session 2.

The one idea to plant now is the deployment version. When someone says the report reads
differently this month, the first question is whether the model changed, and without that
column the question has no answer.
""")

    # ---------------------------------------------------------------- 22
    s = section_slide(prs, 4, "Choosing a tool chain",
                      "Three problem patterns, and the honest criteria for picking between them",
                      icon="compass", duration="1:25  ·  30 min")
    notes(s, """
This block produces the most durable takeaway of Session 1, because it applies to every request
these people get, not only to this pipeline.
""")

    # ---------------------------------------------------------------- 23
    s = steps_slide(
        prs, "Ask three questions, and stop at the first clear answer",
        [
            ("Is the data tabular with a known schema",
             "If yes, take the lowest-code option that handles it. You will maintain whatever you choose.", "Question 1"),
            ("Does it need per-file, per-scene or per-geometry work",
             "If yes, you need code, which means a Spark notebook. Nothing else can open the file.", "Question 2"),
            ("Does it need judgement over unstructured content",
             "If yes, and only if yes, a language model belongs in the chain.", "Question 3"),
        ],
        kicker="Block 4", icon="compass", page=page(), total=TOTAL,
    )
    notes(s, """
Emphasise the order. Starting at question three is how organisations end up asking a model to
do arithmetic, and it happens because question three is the interesting one.

The parenthetical in question one is the real content: you will maintain whatever you choose,
and a notebook is a permanent commitment of somebody's attention.
""")

    # ---------------------------------------------------------------- 24
    s = table_slide(
        prs, "Three patterns and their defaults",
        ["Pattern", "Reach for", "Do not reach for"],
        [
            ["Tabular, known schema,\nscheduled refresh", "Dataflow Gen2 to land it,\nT-SQL to transform",
             "A Spark notebook, because\nyou own it forever"],
            ["Raster or vector geospatial,\nper-scene processing", "Spark notebook with GeoPandas,\nrioxarray and rasterio",
             "Dataflows, which have\nno raster story at all"],
            ["Unstructured text or images,\njudgement calls", "A Foundry model behind a\nnotebook or function",
             "A trained classifier you must\nlabel data for this quarter"],
        ],
        widths=[1.6, 2.0, 2.0],
        kicker="Block 4", icon="filter", page=page(), total=TOTAL, size=12,
        footnote="There is a fourth option that wins more often than any of these: no new tool, because a lookup already answers it.",
    )
    notes(s, """
The footnote is the slide. Ask how many current projects would disappear if someone had asked
whether a lookup table answered the question, and let the silence do the work.
""")

    # ---------------------------------------------------------------- 25
    s = cards_slide(
        prs, "Exercise: pick a chain and defend it",
        [
            ("table", "Card 1  ·  Scaling data",
             "40,000 rows a month from the scaling contractor. Same columns every month. Join to the "
             "block register, refresh by the third."),
            ("satellite", "Card 2  ·  Canopy closure",
             "Which planted stands from the last five years show lower than expected canopy closure, "
             "from imagery, quarterly, full licence area."),
            ("notebook", "Card 3  ·  Field notes",
             "12,000 free-text field notes. Each mentions a block id somewhere. Link them to the "
             "register so a supervisor can browse by block."),
            ("copilot", "Card 4  ·  Tooltip summary",
             "A two-sentence plain-language condition summary per stand, from the twelve numeric "
             "columns the pipeline already produces."),
        ],
        kicker="Block 4", icon="lightbulb", page=page(), total=TOTAL, columns=2,
        subtitle="Two minutes at your table, one minute to defend. One of these is a trap.",
    )
    notes(s, """
Card 3 is the trap and it catches most rooms. Free text triggers the language model reflex, but
block ids follow a fixed format, so a regular expression extracts them at near-perfect accuracy,
for free, deterministically, and it can be unit tested.

A model is justified only for the residue the pattern misses, and only if that residue matters.

Card 4 is the honest yes. Structured input, prose output, value in readability rather than
calculation.
""")

    # ---------------------------------------------------------------- 26
    s = quote_slide(
        prs,
        "\u201cI reach for a notebook when the data will not open any other way.\nI reach for a model when the output is language and the numbers\ncome from somewhere I already trust. Otherwise I reach for the\nlowest-code option a colleague can maintain without me.\u201d",
        "Write your own version of this before the break, and keep it",
        page=page(), total=TOTAL,
    )
    notes(s, """
Give them ninety seconds to write it in their own words. Something written in your own handwriting
survives a workshop; something on a slide does not.

Then break.
""")

    # ---------------------------------------------------------------- 27
    s = section_slide(prs, 5, "Break", "Fifteen minutes. Facilitators are unblocking the pre-flight failures",
                      icon="clock", accent=SILVER, duration="1:55  ·  15 min")
    notes(s, """
Use this window on the people parked on a fallback tier at 0:20. That is the whole purpose of
this break for you.
""")

    # ---------------------------------------------------------------- 28
    s = section_slide(prs, 6, "Fabric and OneLake",
                      "Workspaces, Lakehouse, shortcuts, and the SQL analytics endpoint",
                      icon="lakehouse", duration="2:10  ·  40 min")
    notes(s, """
The conceptual core of the day. Everything after this is application.
""")

    # ---------------------------------------------------------------- 29
    s = flow_slide(
        prs, "OneLake in one picture",
        [
            ("lakehouse", "One storage account", "One data lake for the whole tenant. Every workspace has a folder in it.", GREEN),
            ("shortcut", "Referenced, not copied", "A shortcut points at data anywhere, with no copy and no second refresh.", BLUE),
            ("table", "Many engines", "Spark, T-SQL and Power BI read the same Delta files with no load step.", GOLD),
        ],
        kicker="Block 6", icon="lakehouse", page=page(), total=TOTAL,
        footnote="Most of the copying in a typical estate exists to move data between engines. This removes the reason for it.",
    )
    notes(s, """
Ask how many copies of the stand register exist across the organisation today. The number is
always uncomfortable and always instructive.

Then make the honest caveat: OneLake removes the technical reason for copies. It does not remove
the organisational ones, and those are harder.
""")

    # ---------------------------------------------------------------- 30
    s = cards_slide(
        prs, "Anatomy of a Lakehouse",
        [
            ("download", "Files/",
             "Anything at all. GeoTIFFs, JSON, a zip somebody sent you. Bronze rasters live here."),
            ("table", "Tables/",
             "Delta only. A table is a folder of Parquet plus a transaction log, which is where atomicity "
             "and time travel come from."),
            ("shortcut", "Shortcuts",
             "A reference to data elsewhere, in another workspace or another cloud. Permissions follow "
             "the source, not the shortcut."),
            ("code", "SQL analytics endpoint",
             "Read-only T-SQL over the same files. No storage, no load, no separate model to keep in sync."),
            ("delta", "Time travel",
             "The transaction log lets you read the table as it was. This is what makes bronze auditable."),
            ("gear", "Schemas",
             "Optional grouping inside Tables. Worth turning on if your tenant offers it, awkward to add later."),
        ],
        kicker="Block 6", icon="lakehouse", page=page(), total=TOTAL, columns=3,
    )
    notes(s, """
Dwell on the Tables card. "A table is a folder with a transaction log" is the sentence that
turns Delta from a brand into a mechanism, and once people have it, the rest of the medallion
architecture stops feeling like ceremony.
""")

    # ---------------------------------------------------------------- 31
    s = code_slide(
        prs, "Live demo: shortcut, then query through T-SQL",
        """-- 1.  Create a shortcut from lh_woodlands to the shared reference Lakehouse
--     Tables  >  New shortcut  >  OneLake  >  lh_reference  >  stand_register
--     No copy. No refresh schedule. Nothing moves.

-- 2.  Then, in the SQL analytics endpoint, with no load step at all:

SELECT  species_group,
        COUNT(*)                 AS stands,
        ROUND(SUM(area_ha), 1)   AS total_ha
FROM    stand_register
GROUP BY species_group
ORDER BY total_ha DESC;""",
        caption="The same bytes, written by Spark, referenced by a shortcut, read by T-SQL. "
                "This is usually the moment the OneLake idea lands.",
        kicker="Block 6", icon="shortcut", page=page(), total=TOTAL,
    )
    notes(s, """
Do this live, slowly, and narrate every click. It is the highest-value five minutes in Session 1.

If someone asks about permissions, answer it properly: shortcut access resolves against the
source, so a shortcut cannot be used to widen access to data you could not already read.
""")

    # ---------------------------------------------------------------- 32
    s = table_slide(
        prs, "Where each layer lives",
        ["Layer", "Location", "Write mode", "Why"],
        [
            ["Bronze", "Files/bronze/ and Tables/bronze_*", "Append",
             "Overwriting destroys the ability to explain last month"],
            ["Silver", "Tables/silver_*", "Merge on grain",
             "Re-running a period must replace it, not duplicate it"],
            ["Gold", "Tables/gold_*", "Overwrite per period",
             "Derived and cheap to rebuild from silver"],
            ["Model", "Tables/gold_dim_* and gold_stand_facts", "Overwrite",
             "Star schema, shaped for Direct Lake"],
        ],
        widths=[0.9, 2.4, 1.4, 2.9],
        kicker="Block 6", icon="layers", page=page(), total=TOTAL, size=12,
        footnote="Bronze append-only is the line that pays for itself. A failed run costs time and nothing else.",
    )
    notes(s, """
The footnote is worth expanding. Because bronze never overwrites, a pipeline that dies half way
through is safe to re-run. Without that property, every failure becomes a recovery exercise, and
recovery exercises happen at the worst possible moment.
""")

    # ---------------------------------------------------------------- 33
    s = section_slide(prs, 7, "Hands-on",
                      "Land a Woodlands dataset, reproject it, write a Delta table",
                      icon="notebook", accent=GOLD, duration="2:50  ·  50 min")
    notes(s, """
Everyone opens 00_setup_lakehouse_and_config_STUDENT. Checkpoint at 3:25, hard.

Start a Spark session yourself now if you have not already, so the demo is warm when you need it.
""")

    # ---------------------------------------------------------------- 34
    s = flow_slide(
        prs, "What you are about to build",
        [
            ("compass", "Declare", "Validate the bounding box, then build a stand register in WGS84 degrees.", BRONZE),
            ("globe", "Reproject", "Move to EPSG:2953, the New Brunswick grid, and compute area in hectares.", SILVER),
            ("delta", "Persist", "Geometry as WKB with an srid column, written to Delta and read straight back.", GOLD),
        ],
        kicker="Block 7", icon="notebook", accent=GOLD, page=page(), total=TOTAL,
        footnote="Fifty minutes. The validation cells tell you where you are, so you never have to guess.",
    )
    notes(s, """
Show the notebook on screen while this is up, so people can see the shape of what they are
opening.

Point out that the geometry generator is given to them. The exercise is the coordinate systems
and the attributes, not trigonometry.
""")

    # ---------------------------------------------------------------- 35
    s = table_slide(
        prs, "The three traps, in the order they appear",
        ["Trap", "What you see", "Why it happens"],
        [
            ["geometry column to Delta", "AnalysisException: cannot resolve 'geometry'",
             "Spark has no geometry type. Serialise to WKB, carry the srid separately"],
            ["to_crs on a naive frame", "ValueError: cannot transform naive geometries",
             "GeoPandas refuses to guess, which is correct. Use set_crs to declare, then to_crs"],
            ["Area before reprojection", "Areas like 0.0004",
             "Square degrees. Looks plausible until someone checks it against a cruise sheet"],
            ["set_crs on projected data", "No error at all, geometry in the wrong hemisphere",
             "set_crs relabels without moving anything. This is the dangerous one"],
        ],
        widths=[1.5, 2.5, 3.3],
        kicker="Block 7", icon="warning", accent=AMBER, page=page(), total=TOTAL, size=11.5,
        footnote="Only the last one is silent. Print gdf.crs and gdf.total_bounds before and after every transform.",
    )
    notes(s, """
The fourth row deserves thirty seconds on its own. The first three raise an exception and cost
you five minutes. The fourth produces working code, plausible output, and geometry in the Gulf
of Guinea.

The notebook demonstrates it deliberately in Step 4, so tell them to actually read that cell's
output rather than running past it.
""")

    # ---------------------------------------------------------------- 36
    s = code_slide(
        prs, "The checkpoint at 3:25",
        """[PASS] register is not empty                    120 stands
[PASS] CRS is the analysis projection          EPSG:2953
[PASS] stand_id is unique
[PASS] all expected columns present
[PASS] areas are plausible                     18.4 to 41.2 ha
[PASS] natural stands have no planting year
[PASS] row count survives the round trip       120 vs 120
[PASS] areas match after the round trip        max drift 0.00e+00 ha""",
        caption="Every FAIL is a specific, named thing. Open the solution for that step, read it, carry on. "
                "Nobody sits on a red line while the room moves.",
        kicker="Block 7", icon="check", accent=GOLD, page=page(), total=TOTAL,
    )
    notes(s, """
Show a failing run as well as this one if you have time. A room that has only ever seen green
output does not know what a failure looks like or what to do about it.

Repeat the rule: a FAIL at the checkpoint means open the solution. It is not a judgement, it is
the schedule.
""")

    # ---------------------------------------------------------------- 37
    s = section_slide(prs, 8, "Wrap and homework", "What we covered, and what to do before Session 2",
                      icon="book", duration="3:40  ·  20 min")
    notes(s, "Twenty minutes, and the homework brief needs ten of them. Keep the recap tight.")

    # ---------------------------------------------------------------- 38
    s = bullets_slide(
        prs, "What we covered",
        [
            "Bronze keeps faith with what arrived, silver makes things comparable, gold means something to someone",
            "One storage account, many engines, and a shortcut instead of a copy",
            "Area and distance are only meaningful in a projected coordinate system, and set_crs is not to_crs",
            "Geometry travels through Delta as WKB with the srid in its own column, always",
            "The tool chain question is answered in three steps, and you stop at the first clear answer",
        ],
        kicker="Block 8", icon="check", page=page(), total=TOTAL,
    )
    notes(s, """
Ask the room to add one thing you did not list. Whatever comes back tells you what actually
landed today, which is more useful than your own summary.
""")

    # ---------------------------------------------------------------- 39
    s = steps_slide(
        prs, "Homework, about 45 minutes",
        [
            ("Choose your area of interest",
             "A block you know, roughly 10 to 40 km on a side. Get the bounding box from the "
             "Planetary Computer Explorer.", "15 min"),
            ("Check imagery availability",
             "Sentinel-2 L2A, last growing season, 20 percent cloud or less. You want at least "
             "three scenes over your box.", "15 min"),
            ("Land your stand register",
             "Re-run notebook 00 with your bounding box. Then check the areas against stands "
             "you actually know.", "15 min"),
        ],
        kicker="Block 8", icon="calendar", page=page(), total=TOTAL,
    )
    notes(s, """
The plausibility check in task three is the real exercise. If synthetic stands come out at 4,000
hectares each, something is wrong with the projection, and finding that now is much cheaper than
finding it after a classifier has been built on top.

If you find fewer than three scenes, widen the date range before widening the cloud threshold.
A clear scene from a slightly different week beats a cloudy one from the right week.
""")

    # ---------------------------------------------------------------- 40
    s = flow_slide(
        prs, "Session 2, in five steps",
        [
            ("satellite", "Get it", "STAC search, signing, windowed reads, bronze catalogue.", BRONZE),
            ("filter", "Analyse it", "Mask, scale, reproject, index, zonal statistics.", SILVER),
            ("brain", "Add AI", "Where it earns its place, and where it is quietly wrong.", BLUE),
            ("chart", "Publish it", "Star schema, Direct Lake, a map a planner can filter.", GOLD),
            ("refresh", "Repeat it", "Parameters, schedule, quality gate, failure notification.", GREEN),
        ],
        kicker="Next session", icon="rocket", page=page(), total=TOTAL,
        footnote="Bring your bounding box, your scene count, and one real question about your own data.",
    )
    notes(s, """
Set the expectation that Session 2 is mostly hands on keyboard. Today was the concepts; next
time we build.

Also set the expectation for the AI block honestly: it is as much about where not to use a model
as where to use one, and that block tends to generate the best discussion of the two days.
""")

    # ---------------------------------------------------------------- 41
    s = closing_slide(
        prs, "Before you leave",
        [
            "Confirm your workspace name and Lakehouse are saved somewhere you will find them",
            "Note your bounding box, or plan the fifteen minutes to find one",
            "Post any unresolved blocker in the Teams channel today, not on the morning of Session 2",
            "Bring the one question about your own data. It is the most useful thing in your bag",
        ],
        "Session 2  ·  Build it end to end  ·  Four hours  ·  See you then",
        icon="handoff",
    )
    notes(s, """
Close by collecting one question per person, out loud or on a card. Those questions open Session
2 and they are worth more than any opening slide you could write.
""")

    return prs


if __name__ == "__main__":
    deck = build()
    assert len(deck.slides) == TOTAL, (
        f"slide count drifted: built {len(deck.slides)}, page numbers assume {TOTAL}"
    )
    path = save(deck, "session-1-environment-and-foundations.pptx")
    summarise(deck, path)
