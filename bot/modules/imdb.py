#!/usr/bin/env python3
from contextlib import suppress
from re import findall, IGNORECASE
from pycountry import countries as conn

# Removed Cinemagoer, imported imdbio
from imdbio import IMDb

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

# Initialize imdbio client (Adjust instantiation based on imdbio's exact docs)
imdb_client = IMDb()

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
            # Fetch details via imdbio
            if movie := imdb_client.get_details(movieid): 
                buttons.ibutton(f"🎬 {movie.get('title')} ({movie.get('year')})", f"imdb {user_id} movie {movieid}")
            else:
                return await editMessage(k, "<i>No Results Found</i>")
        else:
            movies = get_poster(title, bulk=True)
            if not movies:
                return await editMessage(k, "<i>No Results Found</i>, Try Again or Use <b>Title ID</b>")
            for movie in movies:
                # Assuming imdbio returns an 'id' key instead of a movieID attribute
                movie_id = movie.get('id', movie.get('imdbID', ''))
                buttons.ibutton(f"🎬 {movie.get('title')} ({movie.get('year')})", f"imdb {user_id} movie {movie_id}")
        
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
            
        # Search via imdbio
        search_results = imdb_client.search(title.lower())
        if not search_results:
            return None
            
        if year:
            filtered = list(filter(lambda k: str(k.get('year')) == str(year), search_results)) or search_results
        else:
            filtered = search_results
            
        # Adjust 'kind' check based on imdbio's specific response values
        filtered = list(filter(lambda k: k.get('kind', '').lower() in ['movie', 'tv series', 'tv'], filtered)) or filtered
        
        if bulk:
            return filtered
            
        movieid = filtered[0].get('id', filtered[0].get('imdbID'))
    else:
        movieid = query
        
    # Fetch specific movie details via imdbio
    movie = imdb_client.get_details(movieid)
    
    if movie.get("original air date"):
        date = movie["original air date"]
    elif movie.get("year"):
        date = movie.get("year")
    else:
        date = "N/A"
        
    plot = movie.get('plot')
    if isinstance(plot, list) and len(plot) > 0:
        plot = plot[0]
    elif not plot:
        plot = movie.get('plot outline', '')
        
    if plot and len(plot) > 300:
        plot = f"{plot[:300]}..."
        
    # NOTE: You MUST verify these keys against imdbio's output. 
    # Cinemagoer keys like 'full-size cover url' or 'number of seasons' likely differ in imdbio.
    return {
        'title': movie.get('title'),
        'trailer': movie.get('videos'),
        'votes': movie.get('votes'),
        "aka": list_to_str(movie.get("akas")),
        "seasons": movie.get("number of seasons"),
        "box_office": movie.get('box office'),
        'localized_title': movie.get('localized title'),
        'kind': movie.get("kind"),
        "imdb_id": f"tt{movie.get('id', movieid).replace('tt', '')}",
        "cast": list_to_str(movie.get("cast")),
        "runtime": list_to_str([get_readable_time(int(run) * 60) for run in movie.get("runtimes", ["0"])]),
        "countries": list_to_hash(movie.get("countries"), True),
        "certificates": list_to_str(movie.get("certificates")),
        "languages": list_to_hash(movie.get("languages")),
        "director": list_to_str(movie.get("director")),
        "writer": list_to_str(movie.get("writer")),
        "producer": list_to_str(movie.get("producer")),
        "composer": list_to_str(movie.get("composer")) ,
        "cinematographer": list_to_str(movie.get("cinematographer")),
        "music_team": list_to_str(movie.get("music department")),
        "distributors": list_to_str(movie.get("distributors")),
        'release_date': date,
        'year': movie.get('year'),
        'genres': list_to_hash(movie.get("genres"), emoji=True),
        'poster': movie.get('cover url', movie.get('poster')), # Updated common key assumption
        'plot': plot,
        'rating': str(movie.get("rating", "N/A")) + " / 10",
        'url': f"https://www.imdb.com/title/tt{movieid.replace('tt', '')}",
        'url_cast': f"https://www.imdb.com/title/tt{movieid.replace('tt', '')}/fullcredits#cast",
        'url_releaseinfo': f"https://www.imdb.com/title/tt{movieid.replace('tt', '')}/releaseinfo",
    }

def list_to_str(k):
    if not k:
        return ""
    elif len(k) == 1:
        return str(k[0])
    elif LIST_ITEMS:
        k = k[:int(LIST_ITEMS)]
        return ' '.join(f'{elem},' for elem in k)[:-1]+' ...'
    else:
        return ' '.join(f'{elem},' for elem in k)[:-1]

def list_to_hash(k, flagg=False, emoji=False):
    listing = ""
    if not k:
        return ""
    elif len(k) == 1:
        if not flagg:
            if emoji:
                return str(IMDB_GENRE_EMOJI.get(k[0], '')+" #"+k[0].replace(" ", "_").replace("-", "_"))
            return str("#"+k[0].replace(" ", "_").replace("-", "_"))
        try:
            conflag = (conn.get(name=k[0])).flag
            return str(f"{conflag} #" + k[0].replace(" ", "_").replace("-", "_"))
        except AttributeError:
            return str("#"+k[0].replace(" ", "_").replace("-", "_"))
    elif LIST_ITEMS:
        k = k[:int(LIST_ITEMS)]
        for elem in k:
            ele = elem.replace(" ", "_").replace("-", "_")
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
            ele = elem.replace(" ", "_").replace("-", "_")
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
