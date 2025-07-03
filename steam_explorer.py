import streamlit as st
import requests
import pandas as pd
import seaborn as sns
import matplotlib.pyplot as plt
import json

params = {
    'json': 1,
    'language': 'english',
    'cursor': "*",  # set the cursor to retrieve reviews from a specific "page"
    'num_per_page': 100,
    'filter': 'recent'
}


def load_games_df() -> pd.DataFrame:
    """Load the static table of game ids, titles, and cost into memory as a dataframe"""
    with open("steam-top-1000.json") as ifp:
        d = json.loads(ifp.read())
    d_as_array = [v for k, v in d.items()]
    df = pd.DataFrame(d_as_array)
    df["name_lowercase"] = df.name.apply(lambda x: x.lower())
    return df

# Do this once, could probably keep in st.session_state
games_df = load_games_df()


def get_user_reviews_helper(steam_app_id, params) -> dict:
    """Query steam to get user reviews"""
    user_review_url = f'https://store.steampowered.com/appreviews/{steam_app_id}'
    req_user_review = requests.get(
        user_review_url,
        params=params
    )

    if req_user_review.status_code != 200:
        st.write(f'Failed to get response. Status code: {req_user_review.status_code}')
        raise ValueError

    try:
        reviews_response = req_user_review.json()
    except Exception as exc:
        st.write(f"Encountered exception: {exc}")
        raise exc

    return reviews_response


def get_user_reviews(steam_app_id: int, params: dict, max_revs = 100) -> list:
    """Iterate through pages of review responses and return them as a list
    Args:
        steam_app_id (int): The unique identifier for the game according to Steam
        params (dict): Dictionary of parameters for querying. These are passed to `get_reviews_helper` and are used to
            advance the current page in the response, as well as set the max reviews
        max_revs (int): Maximum number of reviews to fetch
    """
    revs = []
    while len(revs) < max_revs - 1:
        response = get_user_reviews_helper(steam_app_id, params)
        cursor = response.get("cursor")
        if not cursor:
            break
        revs.extend(response["reviews"])
        # set cursor to move to the next page
        params['cursor'] = cursor
    return revs


def get_steam_app_id(df, search_str):
    games = df[df.name_lowercase.str.contains(search_str.lower())]
    return games[["name", "appid"]]


def parse_reviews(reviews, title) -> pd.DataFrame:
    """Parse the output of the reviews jsons into a DataFrame"""
    data = [
        {
            "playtime": i["author"]["playtime_forever"],
            "voted_up":i["voted_up"],
            "title": title
        }
        for i in reviews
    ]
    df = pd.DataFrame(data)
    df["playtime_hours"] = df.playtime / 60
    return df


def playtime_hist(df, liked="liked") -> plt.Figure:
    """Create histogram of playtime stats, return figure for plotting with streamlit.
    Print summary stats along the way.
    """
    summary_stats = df.playtime_hours.describe()
    mean = round(summary_stats["mean"])
    median = round(df.playtime_hours.median())
    mid_range = f"{round(summary_stats["25%"])} - {round(summary_stats["75%"])}"
    name = df.title.values.tolist()[0]
    fig, ax = plt.subplots()
    ax.axvline(median, linewidth=1, color="r", label="median")
    ax.axvline(mean, linewidth=1, color="g", label="mean")
    fig = sns.histplot(df, x="playtime_hours", stat="count", ax=ax, legend=True)
    ax.legend()
    st.write(f"Players who {liked} {name} played between **{mid_range} hours**, averaging **{median} hours**")
    return fig.get_figure()


def main():
    st.title("🚂 Steam Reviews Explorer 🚂")
    st.write("I made this to understand what I'm getting into when purchasing a new game.")
    st.write("How long are players spending with the game?")
    st.write("What is the difference in playtime between players who liked the game and those who did not?")
    st.write(f"""
    ## Steps to use: \n
        1. In the sidebar, enter a game to search. Results based on the 1000 most popular games on Steam will populate below. \n 
        2. Select the game you want from the dropdown. \n 
        3. Click the "Search <game> reviews" button. \n
        4. Enjoy the graphs.
    """
    )
    with st.sidebar:
        game_title = st.text_input("Search game")
        steam_ids = get_steam_app_id(games_df, game_title)
        chosen_idx = st.selectbox("Found these:", steam_ids.index, format_func=lambda x: steam_ids.loc[x, 'name'])
        chosen_game = games_df.loc[chosen_idx]
        total_reviews = st.number_input("Max number of reviews", 100, 500, step=100)


    with st.form("get_reviews") as ff:
        game_name = chosen_game["name"]
        ready = st.form_submit_button(f"Search **{game_name}** reviews")
        if ready:
            review_score = games_df.loc[chosen_idx].positive/(games_df.loc[chosen_idx].positive + games_df.loc[chosen_idx].negative)
            st.write(f"{game_name} has a Steam review score of **{round(review_score*100, 2)}%** as of 7/3/2025")
            reviews = get_user_reviews(chosen_game["appid"], params, max_revs=total_reviews)
            review_df = parse_reviews(reviews, chosen_game["name"])
            pos, neg = review_df[review_df.voted_up == True], review_df[review_df.voted_up == False]
            liked = playtime_hist(pos)
            did_not_like = playtime_hist(neg, liked="did not like")

            fig1 = sns.catplot(
                review_df,
                x="title",
                y="playtime_hours",
                hue="voted_up",
                col="voted_up",
                col_order=(True, False),
                kind="swarm",
            )
            st.pyplot(fig1)
            col1, col2 = st.columns(2)
            col1.pyplot(liked)
            col2.pyplot(did_not_like)


if __name__ == "__main__":
    st.set_page_config(page_title="Steam Reviews Explorer", page_icon=None, layout="wide",)
    main()