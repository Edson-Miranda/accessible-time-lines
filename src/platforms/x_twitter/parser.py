"""
Parser resiliente para respostas JSON das requisições GraphQL do X (antigo Twitter).
Converte os nós de dados recebidos em modelos universais Post.
Puramente funcional e desacoplado de navegador ou interface gráfica.
"""

from datetime import datetime
import email.utils
from typing import Any, Dict, List, Optional
from src.core.models import MediaItem, Post


def _parse_twitter_date(date_str: str) -> tuple[Optional[datetime], str]:
    """Converte 'Wed Oct 14 21:30:00 +0000 2026' em datetime e string amigável."""
    if not date_str:
        return None, ""
    try:
        dt = email.utils.parsedate_to_datetime(date_str)
        # Formata para exibição em português
        formatted = dt.strftime("%d/%m %H:%M")
        return dt, formatted
    except Exception:
        return None, date_str


def _extract_tweet_node(result_obj: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Extrai o nó real do tweet lidando com TweetWithVisibilityResults."""
    if not isinstance(result_obj, dict):
        return None

    typename = result_obj.get("__typename")
    if typename == "TweetWithVisibilityResults":
        return result_obj.get("tweet")
    elif typename == "Tweet":
        return result_obj
    elif "legacy" in result_obj:
        return result_obj
    return None


def _parse_single_tweet(tweet_data: Dict[str, Any]) -> Optional[Post]:
    """Converte um nó de tweet do GraphQL do X em um objeto Post."""
    node = _extract_tweet_node(tweet_data)
    if not node:
        return None

    rest_id = node.get("rest_id")
    if not rest_id:
        return None

    legacy = node.get("legacy", {})
    core = node.get("core", {})
    user_results = core.get("user_results", {}).get("result", {})
    user_core = user_results.get("core", {})
    user_legacy = user_results.get("legacy", {})

    author_name = user_core.get("name") or user_legacy.get("name") or user_results.get("name") or "Usuário Desconhecido"
    author_username = user_core.get("screen_name") or user_legacy.get("screen_name") or user_results.get("screen_name") or "desconhecido"

    # Tratamento de Retweet
    is_retweet = False
    retweeted_by = None
    retweet_status = legacy.get("retweeted_status_result", {}).get("result")
    if retweet_status:
        is_retweet = True
        retweeted_by = author_name
        orig_node = _extract_tweet_node(retweet_status)
        if orig_node:
            node = orig_node
            legacy = node.get("legacy", {})
            orig_user_res = node.get("core", {}).get("user_results", {}).get("result", {})
            orig_user_core = orig_user_res.get("core", {})
            orig_user_legacy = orig_user_res.get("legacy", {})
            author_name = orig_user_core.get("name") or orig_user_legacy.get("name") or orig_user_res.get("name") or author_name
            author_username = orig_user_core.get("screen_name") or orig_user_legacy.get("screen_name") or orig_user_res.get("screen_name") or author_username

    # Texto
    text = legacy.get("full_text", "")
    # Se for retweet, o full_text pode começar com "RT @usuario: "
    if is_retweet and text.startswith(f"RT @{author_username}: "):
        text = text[len(f"RT @{author_username}: "):]

    # Tratamento de Resposta
    is_reply = False
    replying_to = legacy.get("in_reply_to_screen_name")
    if replying_to:
        is_reply = True

    # Data
    created_at_dt, created_at_str = _parse_twitter_date(legacy.get("created_at", ""))

    # Métricas
    like_count = legacy.get("favorite_count", 0)
    retweet_count = legacy.get("retweet_count", 0)
    reply_count = legacy.get("reply_count", 0)

    # Mídias
    media_items: List[MediaItem] = []
    entities_media = legacy.get("entities", {}).get("media", [])
    extended_media = legacy.get("extended_entities", {}).get("media", [])
    all_media = extended_media or entities_media

    for m in all_media:
        m_type = m.get("type", "image")
        if m_type == "photo":
            m_type = "image"
        m_url = m.get("media_url_https", "")
        alt_text = m.get("ext_alt_text")
        if m_url:
            media_items.append(MediaItem(media_type=m_type, url=m_url, alt_text=alt_text))

    # URLs das entidades
    urls: List[str] = []
    entities_urls = legacy.get("entities", {}).get("urls", [])
    for u in entities_urls:
        target = u.get("expanded_url") or u.get("url")
        if target and target not in urls:
            urls.append(target)

    post_url = f"https://x.com/{author_username}/status/{rest_id}"

    return Post(
        id=str(rest_id),
        platform="x_twitter",
        author_name=author_name,
        author_username=author_username,
        text=text,
        created_at=created_at_dt,
        created_at_str=created_at_str,
        like_count=like_count,
        retweet_count=retweet_count,
        reply_count=reply_count,
        media_items=media_items,
        urls=urls,
        url=post_url,
        is_retweet=is_retweet,
        retweeted_by=retweeted_by,
        is_reply=is_reply,
        replying_to=replying_to,
    )


def parse_x_graphql_response(payload: Dict[str, Any]) -> List[Post]:
    """
    Varre recursivamente o payload da resposta GraphQL do X
    buscando e extraindo postagens encontradas nas instruções da timeline,
    suportando também estruturas com globalObjects.
    """
    posts: List[Post] = []
    seen_ids = set()

    # Suporte a respostas de notificações / API legada com globalObjects
    if isinstance(payload, dict) and "globalObjects" in payload:
        global_objects = payload.get("globalObjects", {})
        if isinstance(global_objects, dict):
            tweets_dict = global_objects.get("tweets", {})
            users_dict = global_objects.get("users", {})
            for tid, t_legacy in tweets_dict.items():
                if tid in seen_ids:
                    continue
                u_id = str(t_legacy.get("user_id_str") or t_legacy.get("user_id") or "")
                u_obj = users_dict.get(u_id, {})
                simulated_node = {
                    "rest_id": str(tid),
                    "legacy": t_legacy,
                    "core": {
                        "user_results": {
                            "result": {
                                "legacy": {
                                    "name": u_obj.get("name", "Usuário Desconhecido"),
                                    "screen_name": u_obj.get("screen_name", "desconhecido"),
                                }
                            }
                        }
                    }
                }
                p = _parse_single_tweet(simulated_node)
                if p and p.id not in seen_ids:
                    seen_ids.add(p.id)
                    posts.append(p)

    def walk_and_find_tweets(data: Any):
        if not isinstance(data, (dict, list)):
            return

        if isinstance(data, dict):
            # Se encontrar tweet_results diretamente
            if "tweet_results" in data:
                tr = data.get("tweet_results", {})
                res = tr.get("result")
                if res:
                    p = _parse_single_tweet(res)
                    if p and p.id not in seen_ids:
                        seen_ids.add(p.id)
                        posts.append(p)

            # Também pode ser tweetResult
            if "tweetResult" in data:
                tr = data.get("tweetResult", {})
                res = tr.get("result")
                if res:
                    p = _parse_single_tweet(res)
                    if p and p.id not in seen_ids:
                        seen_ids.add(p.id)
                        posts.append(p)

            for key, value in data.items():
                walk_and_find_tweets(value)

        elif isinstance(data, list):
            for item in data:
                walk_and_find_tweets(item)

    walk_and_find_tweets(payload)
    return posts
