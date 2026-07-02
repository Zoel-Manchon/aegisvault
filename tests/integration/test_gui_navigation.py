"""Navigation/router behavior stays independent from Qt widgets."""

from ferrovault.adapters.inbound.gui.view_models.navigation import (
    ALL_CATEGORY_LABEL,
    AppNavigationRouter,
)


def test_navigation_router_normalizes_unknown_sections():
    router = AppNavigationRouter(initial_section="Unknown")

    assert router.section == "Vault"
    route = router.navigate("Nope")

    assert route.section == "Vault"
    assert route.is_dashboard is False
    assert route.reset_category_filter is False
    assert route.empty_state.title == "Select an entry"


def test_navigation_router_describes_zero_trust_dashboard_route():
    router = AppNavigationRouter()

    route = router.navigate("Zero Trust")

    assert router.section == "Zero Trust"
    assert route.is_dashboard is True
    assert route.reset_category_filter is True
    assert route.clear_selection is True
    assert route.refresh_overview is True
    assert route.empty_state.title == "Zero Trust control plane"
    assert route.empty_state.show_art is False


def test_navigation_router_describes_category_drilldown():
    router = AppNavigationRouter(initial_section="Categories")

    route = router.open_category("Cloud")

    assert router.section == "Vault"
    assert route.section == "Vault"
    assert route.category == "Cloud"
    assert route.clear_selection is True


def test_navigation_router_uses_safe_category_fallback():
    router = AppNavigationRouter()

    route = router.open_category("")

    assert route.category == ALL_CATEGORY_LABEL
