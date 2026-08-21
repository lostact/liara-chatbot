from langgraph.graph import END, StateGraph
from app.graph.state import ChatState
from app.graph.policies import MAX_RETRIEVAL_LOOPS
from app.graph.nodes.guard_node import guard_node
from app.graph.nodes.hydrate_node import hydrate_node
from app.graph.nodes.route_node import route_node
from app.graph.nodes.clarify_node import clarify_node
from app.graph.nodes.retrieve_node import retrieve_node
from app.graph.nodes.grade_node import grade_node
from app.graph.nodes.expand_node import expand_node
from app.graph.nodes.synthesize_node import synthesize_node
from app.graph.nodes.finalize_node import finalize_node


def route_after_guard(state: ChatState) -> str:
    if state.get("is_shortcut") or not state.get("guard_safe"):
        return "finalize"
    return "hydrate"


def route_after_route(state: ChatState) -> str:
    action = state.get("action", "search")
    if action == "clarify":
        return "clarify"
    if action in ["refuse", "answer_from_context"]:
        return "synthesize"
    return "retrieve"


def route_after_retrieve(state: ChatState) -> str:
    # retrieve_node marks strong RRF agreement as sufficient and can bypass grading.
    if state.get("is_sufficient"):
        return "synthesize"
    return "grade"


def route_after_grade(state: ChatState) -> str:
    is_sufficient = state.get("is_sufficient", True)
    loop_count = state.get("retrieval_loop_count", 0)

    if is_sufficient or loop_count >= MAX_RETRIEVAL_LOOPS:
        return "synthesize"
    return "expand"


def create_chat_graph():
    workflow = StateGraph(ChatState)

    # Register nodes
    workflow.add_node("guard", guard_node)
    workflow.add_node("hydrate", hydrate_node)
    workflow.add_node("route", route_node)
    workflow.add_node("clarify", clarify_node)
    workflow.add_node("retrieve", retrieve_node)
    workflow.add_node("grade", grade_node)
    workflow.add_node("expand", expand_node)
    workflow.add_node("synthesize", synthesize_node)
    workflow.add_node("finalize", finalize_node)

    # Set entry point
    workflow.set_entry_point("guard")

    # Conditional edges
    workflow.add_conditional_edges(
        "guard",
        route_after_guard,
        {
            "finalize": "finalize",
            "hydrate": "hydrate",
        },
    )

    workflow.add_edge("hydrate", "route")

    workflow.add_conditional_edges(
        "route",
        route_after_route,
        {
            "clarify": "clarify",
            "synthesize": "synthesize",
            "retrieve": "retrieve",
        },
    )

    workflow.add_edge("clarify", "finalize")

    workflow.add_conditional_edges(
        "retrieve",
        route_after_retrieve,
        {
            "synthesize": "synthesize",
            "grade": "grade",
        },
    )

    workflow.add_conditional_edges(
        "grade",
        route_after_grade,
        {
            "synthesize": "synthesize",
            "expand": "expand",
        },
    )

    workflow.add_edge("expand", "retrieve")
    workflow.add_edge("synthesize", "finalize")
    workflow.add_edge("finalize", END)

    return workflow.compile()


chat_graph = create_chat_graph()
