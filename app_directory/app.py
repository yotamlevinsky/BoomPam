import streamlit as st
import pandas as pd
import numpy as np
import altair as alt
import random

# ---------------------- State Management ----------------------

def init_state(df=None):
    """Initialize session state variables."""
    if 'df' not in st.session_state or df is not None:
        st.session_state['df'] = df
        st.session_state['unassigned'] = list(df.index) if df is not None else []
        st.session_state['boom'] = []
        st.session_state['pam'] = []
        st.session_state['history'] = []
        st.session_state['current'] = None
        st.session_state['revealed_cards'] = {k: False for k in CARD_KEYS}

def reset_state():
    """Reset the game state, keeping the uploaded CSV."""
    df = st.session_state.get('df')
    init_state(df)

def assign(group):
    """Assign the current person to a group and update history."""
    idx = st.session_state['current']
    if idx is not None:
        st.session_state[group].append(idx)
        st.session_state['history'].append((idx, group))
        st.session_state['current'] = None
        # Remove idx from unassigned if present (fixes bug if not removed earlier)
        if idx in st.session_state['unassigned']:
            st.session_state['unassigned'].remove(idx)

def undo_last():
    """Undo the last assignment."""
    if st.session_state['history']:
        idx, group = st.session_state['history'].pop()
        st.session_state[group].remove(idx)
        st.session_state['unassigned'].append(idx)
        st.session_state['current'] = idx

# ---------------------- Chart Functions ----------------------

def show_chart(key):
    """Display the appropriate chart or stat for a card."""
    df = st.session_state['df']
    if df is None or df.empty:
        st.warning("אין נתונים להצגה.")
        return
    if key == 'avg_age':
        st.metric("גיל ממוצע", f"{df['גיל'].mean():.1f}")
    elif key == 'median_age':
        st.metric("חציון גיל", f"{df['גיל'].median():.1f}")
    elif key == 'scatter_ages':
        # פיזור גילאים: Line chart of age distribution by decade
        max_age = int(df['גיל'].max())
        bins = list(range(0, max_age + 10, 10))
        labels = [f"{b}-{b+10}" for b in bins[:-1]]
        df['decade'] = pd.cut(df['גיל'], bins=bins, labels=labels, right=False, include_lowest=True)
        decade_counts = df['decade'].value_counts().sort_index().reset_index()
        decade_counts.columns = ['decade', 'count']
        chart = alt.Chart(decade_counts).mark_line(point=True, color='red').encode(
            x=alt.X('decade:N', title='גיל בעשורים', axis=alt.Axis(labels=False, ticks=True)),
            y=alt.Y('count:Q', title='כמות אנשים', axis=alt.Axis(labels=False, ticks=True))
        )
        st.altair_chart(chart, use_container_width=True)
    elif key == 'dist_north_south':
        # Blind distribution: vertical bars with gaps, no area names
        df2 = df.copy()
        area_counts = df2['אזור בעיר'].value_counts().reset_index()
        area_counts.columns = ['area', 'count']
        area_counts['idx'] = area_counts.index.astype(str)  # Use index as x-axis
        chart = alt.Chart(area_counts).mark_bar(size=30).encode(
            x=alt.X('idx:N', title='', axis=alt.Axis(labels=False, ticks=False)),
            y=alt.Y('count:Q', title='כמות'),
            color=alt.Color('area:N', legend=None)
        ).properties(width=40 * len(area_counts), height=350)
        st.altair_chart(chart, use_container_width=True)
    elif key == 'corr_female_center':
        # Show two bars: how many females live in center, and how many do not
        df2 = df.copy()
        df2['is_female'] = df2['מין'].replace({'נקבה': 'אישה', 'זכר': 'גבר'}) == 'אישה'
        df2['is_center'] = df2['אזור בעיר'].str.contains('מרכז')
        # Only count females
        females = df2[df2['is_female']]
        center_count = females['is_center'].sum()
        not_center_count = (~females['is_center']).sum()
        bar_df = pd.DataFrame({
            'קבוצה': ['מרכז', 'לא מרכז'],
            'כמות': [center_count, not_center_count]
        })
        chart = alt.Chart(bar_df).mark_bar().encode(
            x=alt.X('קבוצה:N', title=''),
            y=alt.Y('כמות:Q', title='מספר נשים'),
            color=alt.Color('קבוצה:N', scale=alt.Scale(domain=['מרכז','לא מרכז'], range=['#e377c2','#7f7f7f']), legend=None)
        )
        st.altair_chart(chart, use_container_width=True)
    elif key == 'corr_age_south':
        df2 = df.copy()
        df2['is_south'] = df2['אזור בעיר'].str.contains('דרום')
        chart = alt.Chart(df2).mark_circle(size=60).encode(
            x=alt.X('is_south:O', title='דרום'),
            y=alt.Y('גיל:Q', title='גיל'),
            color='is_south:N',
            tooltip=['שם', 'גיל', 'אזור בעיר']
        )
        st.altair_chart(chart, use_container_width=True)

# ---------------------- Card Config ----------------------

CARD_KEYS = [
    'avg_age', 'median_age', 'scatter_ages',
    'dist_north_south', 'corr_female_center', 'corr_age_south'
]
CARD_TITLES = {
    'avg_age': 'גיל ממוצע',
    'median_age': 'חציון גיל',
    'scatter_ages': 'פיזור גילאים',
    'dist_north_south': 'התפלגות צפון/דרום',
    'corr_female_center': 'נקבה מול מרכז',
    'corr_age_south': 'גיל מול דרום'
}
CARD_ICONS = {
    'avg_age': '🔒',
    'median_age': '🔒',
    'scatter_ages': '🔒',
    'dist_north_south': '🔒',
    'corr_female_center': '🔒',
    'corr_age_south': '🔒'
}

# ---------------------- UI Functions ----------------------

def sidebar():
    """Sidebar with file uploader and reset button."""
    st.sidebar.title("הגדרות")
    uploaded = st.sidebar.file_uploader("העלה קובץ CSV", type=['csv'])
    # Only initialize when we haven't already stored this file
    if uploaded and 'df' not in st.session_state:
        df = pd.read_csv(uploaded)[["שם", "מין", "גיל", "אזור בעיר"]].reset_index(drop=True)
        init_state(df)
    if st.sidebar.button("איפוס משחק"):
        reset_state()

def show_tables():
    """Display BOOM and PAM tables side by side, with local images above."""
    df = st.session_state['df']
    boom = df.loc[st.session_state['boom']] if st.session_state['boom'] else pd.DataFrame(columns=df.columns)
    pam = df.loc[st.session_state['pam']] if st.session_state['pam'] else pd.DataFrame(columns=df.columns)
    col1, col2 = st.columns(2)
    with col1:
        st.image("https://raw.githubusercontent.com/yotamlevinsky/BoomPam/refs/heads/main/app_directory/images/Boom.png", caption="BOOM", use_container_width=True)
        st.subheader("BOOM")
        st.dataframe(boom, use_container_width=True, hide_index=True)
    with col2:
        st.image("https://raw.githubusercontent.com/yotamlevinsky/BoomPam/refs/heads/main/app_directory/images/Pam.png", caption="PAM", use_container_width=True)
        st.subheader("PAM")
        st.dataframe(pam, use_container_width=True, hide_index=True)

def show_draw_and_assign():
    """Draw a random person and assign to group."""
    df = st.session_state['df']
    if st.button("שלוף דמות רנדומלית"):
        if st.session_state['unassigned']:
            idx = random.choice(st.session_state['unassigned'])
            st.session_state['unassigned'].remove(idx)
            st.session_state['current'] = idx
        else:
            st.info("אין דמויות נוספות לשליפה.")
    if st.session_state.get('current') is not None:
        idx = st.session_state['current']
        person = df.loc[idx]
        st.markdown(f"**{person['שם']}** | גיל: {person['גיל']} | מין: {person['מין']} | אזור: {person['אזור בעיר']}")
        col1, col2, col3 = st.columns([1,1,1])
        with col1:
            if st.button("→ BOOM"):
                assign('boom')
        with col2:
            if st.button("→ PAM"):
                assign('pam')
        with col3:
            if st.button("Undo"):
                undo_last()

def show_cards():
    st.markdown("### קלפים סטטיסטיים")
    if 'revealed_cards' not in st.session_state:
        st.session_state['revealed_cards'] = {k: False for k in CARD_KEYS}
    cols = st.columns(3, gap="large")
    for i, key in enumerate(CARD_KEYS):
        with cols[i % 3]:
            if not st.session_state['revealed_cards'][key]:
                if st.button(f"{CARD_ICONS[key]}\n{CARD_TITLES[key]}", key=key, help=CARD_TITLES[key]):
                    st.session_state['revealed_cards'][key] = True
            else:
                show_chart(key)

# --- Sample Cards ---
SAMPLE_CARD_KEYS = ['sample5', 'sample10', 'sample5_undrawn']
SAMPLE_CARD_TITLES = {
    'sample5': 'Sample of 5',
    'sample10': 'Sample of 10',
    'sample5_undrawn': 'Sample of 5 (undrawn)'
}

def show_sample_card(title, sample_df):
    if sample_df.empty:
        st.warning("אין נתונים להצגה.")
        return
    max_age = int(sample_df['גיל'].max())
    bins = list(range(0, max_age + 10, 10))
    labels = [f"{b}-{b+10}" for b in bins[:-1]]
    sample_df = sample_df.copy()
    sample_df['decade'] = pd.cut(sample_df['גיל'], bins=bins, labels=labels, right=False, include_lowest=True)
    # Ensure all columns exist and are strings
    sample_df['אזור בעיר'] = sample_df['אזור בעיר'].astype(str)
    sample_df['מין'] = sample_df['מין'].astype(str)
    chart = alt.Chart(sample_df).mark_circle(size=120).encode(
        x=alt.X('decade:O', title='גיל בעשורים', axis=alt.Axis(labels=False, ticks=True)),
        y=alt.Y('אזור בעיר:N', title='אזור בעיר', axis=alt.Axis(labels=False, ticks=True)),
        color=alt.Color('מין:N', scale=alt.Scale(domain=['גבר', 'אישה'], range=['blue', 'red']), legend=None),
        tooltip=['שם', 'גיל', 'מין', 'אזור בעיר']
    ).properties(title=title, height=250)
    st.altair_chart(chart, use_container_width=True)

def show_sample_cards():
    df = st.session_state['df']
    # initialize reveal-state only once
    if 'revealed_sample_cards' not in st.session_state:
        st.session_state['revealed_sample_cards'] = {
            'sample5': False,
            'sample10': False,
            'sample5_undrawn': False
        }
    cols = st.columns(3, gap="large")
    for col, key, n in zip(cols, ['sample5','sample10','sample5_undrawn'], [5, 10, None]):
        title = {
            'sample5': "Sample of 5",
            'sample10': "Sample of 10",
            'sample5_undrawn': "Sample of 5 (undrawn)"
        }[key]
        with col:
            if not st.session_state['revealed_sample_cards'][key]:
                if st.button(f"🔍 {title}", key=f"btn_{key}"):
                    st.session_state['revealed_sample_cards'][key] = True
            else:
                # build the proper index list
                if key in ['sample5','sample10']:
                    if len(df) >= (n or 0):
                        idxs = random.sample(list(df.index), n)
                    else:
                        idxs = []
                else:  # sample5_undrawn
                    unassigned = st.session_state.get('unassigned', [])
                    idxs = random.sample(unassigned, 5) if len(unassigned) >= 5 else []
                # DEBUG: make sure we really sampled
                sample_df = df.loc[idxs].reset_index(drop=True)
                st.write("DEBUG sample_df:", sample_df)
                # now chart it
                if not sample_df.empty:
                    show_sample_chart(key, sample_df)

def show_sample_chart(key, sample_df):
    bins = list(range(0, int(sample_df['גיל'].max()) + 10, 10))
    labels = [f"{b}-{b+10}" for b in bins[:-1]]
    sample_df = sample_df.copy()
    sample_df['decade'] = pd.cut(sample_df['גיל'], bins=bins, labels=labels, right=False)
    # Normalize gender values to 'גבר'/'אישה' for color
    sample_df['מין'] = sample_df['מין'].replace({'נקבה': 'אישה', 'זכר': 'גבר'}).astype(str)
    # Make chart bigger and fix axis titles
    chart = (
        alt.Chart(sample_df)
           .mark_circle(size=250)
           .encode(
             x=alt.X('decade:O', title='גיל בעשורים', axis=alt.Axis(labels=True, ticks=True)),
             y=alt.Y('אזור בעיר:N', title='אזור בעיר', axis=alt.Axis(labels=True, ticks=True)),
             color=alt.Color('מין:N', scale=alt.Scale(domain=['גבר','אישה'], range=['blue','red']), legend=None),
             tooltip=['שם','גיל','מין','אזור בעיר']
           )
           .properties(height=400, width=350)
    )
    st.altair_chart(chart, use_container_width=True)

# ---------------------- Main App ----------------------

def main():
    st.set_page_config(page_title="משחק BOOM-PAM", layout="wide")
    sidebar()
    if st.session_state.get('df') is not None:
        show_tables()
        st.divider()
        show_draw_and_assign()
        st.divider()
        show_cards()
        st.divider()
        show_sample_cards()
    else:
        st.info("אנא העלה קובץ CSV עם העמודות: שם, מין, גיל, אזור בעיר.")

if __name__ == "__main__":
    main()