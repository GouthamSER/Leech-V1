#!/usr/bin/env python3
from contextlib import suppress
from re import findall, IGNORECASE
from pycountry import countries as conn

# Correctly importing the top-level functions from imdbio
from imdbio import search_title, get_movie

from pyrogram.handlers import MessageHandler, CallbackQueryHandler
from pyrogram.filters import command, regex
from pyrogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from pyrogram.errors import MediaEmpty, PhotoInvalidDimensions, WebpageMediaEmpty

from bot import bot, LOGGER, user_data, config_dict
from bot.helper.telegram_helper.filters import CustomFilters
from bot.helper.telegram_helper.bot_commands import BotCommands
from bot.helper.telegram_helper.message_utils import sendMessage, editMessage
from bot.helper.ext_utils.bot_utils import get_readable_time
from bot.helper.telegram_helper.button_build import ButtonMaker

IMDB_GENRE_EMOJI = {"Action": "🚀", "Adult": "🔞", "Adventure": "🌋", "Animation": "🎠", "Biography": "📜", "Comedy": "🪗", "Crime": "🔪", "Documentary": "🎞", "Drama": "🎭", "Family": "👨‍👩‍👧‍👦", "Fantasy": "🫧", "Film Noir": "🎯", "Game Show": "🎮", "History": "🏛", "Horror": "🧟", "Musical": "🎻", "Music": "🎸", "Mystery": "🧳", "News": "📰", "Reality-TV": "🖥", "Romance": "🥰", "Sci-Fi": "🌠", "Short": "📝", "Sport": "⛳", "Talk-Show": "👨‍🍳", "Thriller": "🗡", "War": "⚔", "Western": "🪩"}
LIST_ITEMS = 4

async def imdb_search(_, message):
    if ' ' in message.text:
        k = await sendMessage(message, '<code>Searching IMDB ...</code>')
        title = message.text.split(' ', 1)[1]
        user_id = message.from_user.id
        buttons = ButtonMaker()
        
        if title.lower().startswith("https://www.imdb.com/title/tt"):
            movieid = title.replace("https://www.imdb.com/title/tt", "")
            
            try:
                # Need the 'tt' prefix for get_movie
                movie = get_movie(f"tt{movieid}")
                buttons.ibutton(f"🎬 {movie.title} ({movie.year})", f"imdb {user_id} movie tt{movieid}")
            except Exception:
                return await editMessage(k, "<i>No Results Found</i>")
        else:
            movies = get_poster(title, bulk=True)
            if not movies:
                return await editMessage(k, "<i>No Results Found</i>, Try Again or Use <b>Title ID</b>")
            for movie in movies:
                buttons.ibutton(f"🎬 {movie.title} ({movie.year})", f"imdb {user_id} movie {movie.imdb_id}")
        
        buttons.ibutton("🚫 Close 🚫", f"imdb {user_id} close")
        await editMessage(k, '<b><i>Here What I found on IMDb.com</i></b>', buttons.build_menu(1))
    else:
        await sendMessage(message, '<i>Send Movie / TV Series Name along with /imdb Command or send IMDB URL</i>')


def get_poster(query, bulk=False, id=False, file=None):
    if not id:
        query = (query.strip()).lower()
        title = query
        year = findall(r'[1-2]\d{3}$', query, IGNORECASE)
        
        if year:
            year = list_to_str(year[:1])
            title = (query.replace(year, "")).strip()
        elif file is not None:
            year = findall(r'[1-2]\d{3}', file, IGNORECASE)
            if year:
                year = list_to_str(year[:1]) 
        else:
            year = None
            
        try:
            if year:
                # imdbio supports year filtering directly inside search_title
                search_results = search_title(title.lower(), year=int(year))
            else:
                search_results = search_title(title.lower())
                
            if not search_results or not getattr(search_results, 'titles', None):
                return None
                
            filtered = search_results.titles
        except Exception as e:
            LOGGER.error(f"IMDb search error: {e}")
            return None
        
        if bulk:
            return filtered
            
        movieid = filtered[0].imdb_id
    else:
        movieid = query
        
    try:
        movie_obj = get_movie(movieid)
        # imdbio returns Pydantic objects. Convert them to dictionaries to maintain compatibility
        movie = movie_obj.dict() if hasattr(movie_obj, 'dict') else movie_obj.model_dump() if hasattr(movie_obj, 'model_dump') else vars(movie_obj)
    except Exception as e:
        LOGGER.error(f"IMDb get_movie error: {e}")
        return None
    
    date = movie.get("release_date") or movie.get("year") or "N/A"
        
    plot = movie.get('plot', '') or movie.get('plot_outline', '')
    if isinstance(plot, list) and len(plot) > 0:
        plot = plot[0]
        
    if plot and len(plot) > 300:
        plot = f"{plot[:300]}..."
        
    # Safely extracting lists of actors/directors since they might be nested dicts from Pydantic
    def extract_names(item_list):
        if not item_list: return []
        if isinstance(item_list, dict):
            return [str(val) for val in item_list.values()]
        return [item.get('name', str(item)) if isinstance(item, dict) else str(item) for item in item_list]

    return {
        'title': movie.get('title'),
        'trailer': movie.get('trailer', movie.get('videos')),
        'votes': movie.get('votes', movie.get('num_votes')),
        "aka": list_to_str(movie.get("akas", [])),
        "seasons": movie.get("seasons", movie.get("number_of_seasons")),
        "box_office": movie.get('box_office'),
        'localized_title': movie.get('localized_title'),
        'kind': movie.get("type", movie.get("kind")),
        "imdb_id": movie.get('imdb_id', movieid),
        "cast": list_to_str(extract_names(movie.get("cast", []))),
        "runtime": list_to_str([get_readable_time(int(run) * 60) if str(run).isdigit() else run for run in movie.get("runtimes", ["0"])]),
        "countries": list_to_hash(movie.get("countries", []), True),
        "certificates": list_to_str(movie.get("certificates", [])),
        "languages": list_to_hash(movie.get("languages", [])),
        "director": list_to_str(extract_names(movie.get("directors", movie.get("director", [])))),
        "writer": list_to_str(extract_names(movie.get("writers", movie.get("writer", [])))),
        "producer": list_to_str(extract_names(movie.get("producers", movie.get("producer", [])))),
        "composer": list_to_str(extract_names(movie.get("composers", movie.get("composer", [])))),
        "cinematographer": list_to_str(extract_names(movie.get("cinematographers", movie.get("cinematographer", [])))),
        "music_team": list_to_str(extract_names(movie.get("music_department", []))),
        "distributors": list_to_str(extract_names(movie.get("distributors", []))),
        'release_date': date,
        'year': movie.get('year'),
        'genres': list_to_hash(movie.get("genres", []), emoji=True),
        'poster': movie.get('poster', movie.get('cover_url')), 
        'plot': plot,
        'rating': f'{movie.get("rating", "N/A")} / 10',
        'url': f"https://www.imdb.com/title/{movie.get('imdb_id', movieid)}",
        'url_cast': f"https://www.imdb.com/title/{movie.get('imdb_id', movieid)}/fullcredits#cast",
        'url_releaseinfo': f"https://www.imdb.com/title/{movie.get('imdb_id', movieid)}/releaseinfo",
    }


def list_to_str(k):
    if not k:
        return ""
        
    # If it's a dictionary (like certificates: {"USA": "R"}), convert to list of strings
    if isinstance(k, dict):
        k = [f"{key}: {val}" for key, val in k.items()]
    # If it's a set or other non-list iterable, convert to list
    elif not isinstance(k, list):
        try:
            k = list(k)
        except Exception:
            k = [k]
            
    if len(k) == 0:
        return ""
    elif len(k) == 1:
        return str(k[0])
    elif LIST_ITEMS:
        k = k[:int(LIST_ITEMS)]
        return ' '.join(f'{elem},' for elem in k)[:-1] + ' ...'
    else:
        return ' '.join(f'{elem},' for elem in k)[:-1]


def list_to_hash(k, flagg=False, emoji=False):
    if not k:
        return ""
        
    # Safely convert dicts/sets to lists
    if isinstance(k, dict):
        k = list(k.keys())
    elif not isinstance(k, list):
        try:
            k = list(k)
        except Exception:
            k = [k]
            
    if len(k) == 0:
        return ""
        
    listing = ""
    if len(k) == 1:
        if not flagg:
            if emoji:
                return str(IMDB_GENRE_EMOJI.get(k[0], '') + " #" + str(k[0]).replace(" ", "_").replace("-", "_"))
            return str("#" + str(k[0]).replace(" ", "_").replace("-", "_"))
        try:
            conflag = (conn.get(name=k[0])).flag
            return str(f"{conflag} #" + str(k[0]).replace(" ", "_").replace("-", "_"))
        except AttributeError:
            return str("#" + str(k[0]).replace(" ", "_").replace("-", "_"))
    elif LIST_ITEMS:
        k = k[:int(LIST_ITEMS)]
        for elem in k:
            ele = str(elem).replace(" ", "_").replace("-", "_")
            if flagg:
                with suppress(AttributeError):
                    conflag = (conn.get(name=elem)).flag
                    listing += f'{conflag} '
            if emoji:
                listing += f"{IMDB_GENRE_EMOJI.get(elem, '')} "
            listing += f'#{ele}, '
        return f'{listing[:-2]}'
    else:
        for elem in k:
            ele = str(elem).replace(" ", "_").replace("-", "_")
            if flagg:
                try:
                    conflag = (conn.get(name=elem)).flag
                    listing += f'{conflag} '
                except AttributeError:
                    pass
            listing += f'#{ele}, '
        return listing[:-2]


async def imdb_callback(_, query):
    message = query.message
    user_id = query.from_user.id
    data = query.data.split()
    
    if user_id != int(data[1]):
        await query.answer("Not Yours!", show_alert=True)
    elif data[2] == "movie":
        await query.answer()
        imdb_data = get_poster(query=data[3], id=True)
        buttons = []
        
        if imdb_data and imdb_data.get('trailer'):
            if isinstance(imdb_data['trailer'], list):
                buttons.append([InlineKeyboardButton("▶️ IMDb Trailer ", url=str(imdb_data['trailer'][-1]))])
                imdb_data['trailer'] = list_to_str(imdb_data['trailer'])
            else: 
                buttons.append([InlineKeyboardButton("▶️ IMDb Trailer ", url=str(imdb_data['trailer']))])
                
        buttons.append([InlineKeyboardButton("🚫 Close 🚫", callback_data=f"imdb {user_id} close")])
        template = config_dict.get('IMDB_TEMPLATE', "")
        
        if imdb_data and template != "":
            cap = template.format(
                title = imdb_data['title'],
                trailer = imdb_data['trailer'],
                votes = imdb_data['votes'],
                aka = imdb_data["aka"],
                seasons = imdb_data["seasons"],
                box_office = imdb_data['box_office'],
                localized_title = imdb_data['localized_title'],
                kind = imdb_data['kind'],
                imdb_id = imdb_data["imdb_id"],
                cast = imdb_data["cast"],
                runtime = imdb_data["runtime"],
                countries = imdb_data["countries"],
                certificates = imdb_data["certificates"],
                languages = imdb_data["languages"],
                director = imdb_data["director"],
                writer = imdb_data["writer"],
                producer = imdb_data["producer"],
                composer = imdb_data["composer"],
                cinematographer = imdb_data["cinematographer"],
                music_team = imdb_data["music_team"],
                distributors = imdb_data["distributors"],
                release_date = imdb_data['release_date'],
                year = imdb_data['year'],
                genres = imdb_data['genres'],
                poster = imdb_data['poster'],
                plot = imdb_data['plot'],
                rating = imdb_data['rating'],
                url = imdb_data['url'],
                url_cast = imdb_data['url_cast'],
                url_releaseinfo = imdb_data['url_releaseinfo'],
                **locals()
            )
        else:
            cap = "No Results"
            
        if imdb_data and imdb_data.get('poster'):
            try:
                await bot.send_photo(
                    chat_id=query.message.reply_to_message.chat.id,  
                    caption=cap, 
                    photo=imdb_data['poster'], 
                    reply_to_message_id=query.message.reply_to_message.id, 
                    reply_markup=InlineKeyboardMarkup(buttons)
                )
            except (MediaEmpty, PhotoInvalidDimensions, WebpageMediaEmpty):
                poster = imdb_data.get('poster').replace('.jpg', "._V1_UX360.jpg")
                await sendMessage(message.reply_to_message, cap, InlineKeyboardMarkup(buttons), poster)
        else:
            await sendMessage(message.reply_to_message, cap, InlineKeyboardMarkup(buttons), 'https://telegra.ph/file/5af8d90a479b0d11df298.jpg')
            
        await message.delete()
    else:
        await query.answer()
        await query.message.delete()
        with suppress(Exception):
            await query.message.reply_to_message.delete()


bot.add_handler(MessageHandler(imdb_search, filters=command(BotCommands.IMDBCommand) & CustomFilters.authorized & ~CustomFilters.blacklisted))
bot.add_handler(CallbackQueryHandler(imdb_callback, filters=regex(r'^imdb')))
