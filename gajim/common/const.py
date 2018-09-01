from enum import IntEnum, Enum, unique
from collections import namedtuple

Option = namedtuple('Option', 'kind label type value name callback data desc enabledif props')
Option.__new__.__defaults__ = (None,) * len(Option._fields)

DialogButton = namedtuple('DialogButton', 'text callback action')
DialogButton.__new__.__defaults__ = (None, None)


@unique
class OptionKind(IntEnum):
    ENTRY = 0
    SWITCH = 1
    SPIN = 2
    ACTION = 3
    LOGIN = 4
    DIALOG = 5
    CALLBACK = 6
    PROXY = 7
    HOSTNAME = 8
    PRIORITY = 9
    FILECHOOSER = 10
    CHANGEPASSWORD = 11
    GPG = 12


@unique
class OptionType(IntEnum):
    ACCOUNT_CONFIG = 0
    CONFIG = 1
    VALUE = 2
    ACTION = 3
    DIALOG = 4


class AvatarSize(IntEnum):
    TAB = 16
    ROSTER = 32
    CHAT = 48
    NOTIFICATION = 48
    TOOLTIP = 125
    VCARD = 200
    PUBLISH = 200


class ArchiveState(IntEnum):
    NEVER = 0
    ALL = 1


@unique
class PathLocation(IntEnum):
    CONFIG = 0
    CACHE = 1
    DATA = 2


@unique
class PathType(IntEnum):
    FILE = 0
    FOLDER = 1
    FOLDER_OPTIONAL = 2


@unique
class KindConstant(IntEnum):
    STATUS = 0
    GCSTATUS = 1
    GC_MSG = 2
    SINGLE_MSG_RECV = 3
    CHAT_MSG_RECV = 4
    SINGLE_MSG_SENT = 5
    CHAT_MSG_SENT = 6
    ERROR = 7

    def __str__(self):
        return str(self.value)


@unique
class ShowConstant(IntEnum):
    ONLINE = 0
    CHAT = 1
    AWAY = 2
    XA = 3
    DND = 4
    OFFLINE = 5


@unique
class TypeConstant(IntEnum):
    AIM = 0
    GG = 1
    HTTP_WS = 2
    ICQ = 3
    MSN = 4
    QQ = 5
    SMS = 6
    SMTP = 7
    TLEN = 8
    YAHOO = 9
    NEWMAIL = 10
    RSS = 11
    WEATHER = 12
    MRIM = 13
    NO_TRANSPORT = 14


@unique
class SubscriptionConstant(IntEnum):
    NONE = 0
    TO = 1
    FROM = 2
    BOTH = 3


@unique
class JIDConstant(IntEnum):
    NORMAL_TYPE = 0
    ROOM_TYPE = 1

@unique
class StyleAttr(Enum):
    COLOR = 'color'
    BACKGROUND = 'background'
    FONT = 'font'

@unique
class CSSPriority(IntEnum):
    APPLICATION = 600
    APPLICATION_DARK = 601
    DEFAULT_THEME = 610
    DEFAULT_THEME_DARK = 611
    USER_THEME = 650

@unique
class ButtonAction(Enum):
    DESTRUCTIVE = 'destructive-action'
    SUGGESTED = 'suggested-action'

@unique
class IdleState(IntEnum):
    UNKNOWN = 0
    XA = 1
    AWAY = 2
    AWAKE = 3


@unique
class RequestAvatar(IntEnum):
    SELF = 0
    ROOM = 1
    USER = 2


@unique
class BookmarkStorageType(IntEnum):
    PRIVATE = 0
    PUBSUB = 1


@unique
class PEPHandlerType(IntEnum):
    NOTIFY = 0
    RETRACT = 1


@unique
class PEPEventType(IntEnum):
    ACTIVITY = 0
    TUNE = 1
    MOOD = 2
    LOCATION = 3
    NICKNAME = 4
    AVATAR = 5
    ATOM = 6


ACTIVITIES = {
    'doing_chores': {
        'category': _('Doing Chores'),
        'buying_groceries': _('Buying Groceries'),
        'cleaning': _('Cleaning'),
        'cooking': _('Cooking'),
        'doing_maintenance': _('Doing Maintenance'),
        'doing_the_dishes': _('Doing the Dishes'),
        'doing_the_laundry': _('Doing the Laundry'),
        'gardening': _('Gardening'),
        'running_an_errand': _('Running an Errand'),
        'walking_the_dog': _('Walking the Dog')},
    'drinking': {
        'category': _('Drinking'),
        'having_a_beer': _('Having a Beer'),
        'having_coffee': _('Having Coffee'),
        'having_tea': _('Having Tea')},
    'eating': {
        'category': _('Eating'),
        'having_a_snack': _('Having a Snack'),
        'having_breakfast': _('Having Breakfast'),
        'having_dinner': _('Having Dinner'),
        'having_lunch': _('Having Lunch')},
    'exercising': {
        'category': _('Exercising'),
        'cycling': _('Cycling'),
        'dancing': _('Dancing'),
        'hiking': _('Hiking'),
        'jogging': _('Jogging'),
        'playing_sports': _('Playing Sports'),
        'running': _('Running'),
        'skiing': _('Skiing'),
        'swimming': _('Swimming'),
        'working_out': _('Working out')},
    'grooming': {
        'category': _('Grooming'),
        'at_the_spa': _('At the Spa'),
        'brushing_teeth': _('Brushing Teeth'),
        'getting_a_haircut': _('Getting a Haircut'),
        'shaving': _('Shaving'),
        'taking_a_bath': _('Taking a Bath'),
        'taking_a_shower': _('Taking a Shower')},
    'having_appointment': {
        'category': _('Having an Appointment')},
    'inactive': {
        'category': _('Inactive'),
        'day_off': _('Day Off'),
        'hanging_out': _('Hanging out'),
        'hiding': _('Hiding'),
        'on_vacation': _('On Vacation'),
        'praying': _('Praying'),
        'scheduled_holiday': _('Scheduled Holiday'),
        'sleeping': _('Sleeping'),
        'thinking': _('Thinking')},
    'relaxing': {
        'category': _('Relaxing'),
        'fishing': _('Fishing'),
        'gaming': _('Gaming'),
        'going_out': _('Going out'),
        'partying': _('Partying'),
        'reading': _('Reading'),
        'rehearsing': _('Rehearsing'),
        'shopping': _('Shopping'),
        'smoking': _('Smoking'),
        'socializing': _('Socializing'),
        'sunbathing': _('Sunbathing'),
        'watching_tv': _('Watching TV'),
        'watching_a_movie': _('Watching a Movie')},
    'talking': {
        'category': _('Talking'),
        'in_real_life': _('In Real Life'),
        'on_the_phone': _('On the Phone'),
        'on_video_phone': _('On Video Phone')},
    'traveling': {
        'category': _('Traveling'),
        'commuting': _('Commuting'),
        'cycling': _('Cycling'),
        'driving': _('Driving'),
        'in_a_car': _('In a Car'),
        'on_a_bus': _('On a Bus'),
        'on_a_plane': _('On a Plane'),
        'on_a_train': _('On a Train'),
        'on_a_trip': _('On a Trip'),
        'walking': _('Walking')},
    'working': {
        'category': _('Working'),
        'coding': _('Coding'),
        'in_a_meeting': _('In a Meeting'),
        'studying': _('Studying'),
        'writing': _('Writing')}}

MOODS = {
    'afraid': _('Afraid'),
    'amazed': _('Amazed'),
    'amorous': _('Amorous'),
    'angry': _('Angry'),
    'annoyed': _('Annoyed'),
    'anxious': _('Anxious'),
    'aroused': _('Aroused'),
    'ashamed': _('Ashamed'),
    'bored': _('Bored'),
    'brave': _('Brave'),
    'calm': _('Calm'),
    'cautious': _('Cautious'),
    'cold': _('Cold'),
    'confident': _('Confident'),
    'confused': _('Confused'),
    'contemplative': _('Contemplative'),
    'contented': _('Contented'),
    'cranky': _('Cranky'),
    'crazy': _('Crazy'),
    'creative': _('Creative'),
    'curious': _('Curious'),
    'dejected': _('Dejected'),
    'depressed': _('Depressed'),
    'disappointed': _('Disappointed'),
    'disgusted': _('Disgusted'),
    'dismayed': _('Dismayed'),
    'distracted': _('Distracted'),
    'embarrassed': _('Embarrassed'),
    'envious': _('Envious'),
    'excited': _('Excited'),
    'flirtatious': _('Flirtatious'),
    'frustrated': _('Frustrated'),
    'grateful': _('Grateful'),
    'grieving': _('Grieving'),
    'grumpy': _('Grumpy'),
    'guilty': _('Guilty'),
    'happy': _('Happy'),
    'hopeful': _('Hopeful'),
    'hot': _('Hot'),
    'humbled': _('Humbled'),
    'humiliated': _('Humiliated'),
    'hungry': _('Hungry'),
    'hurt': _('Hurt'),
    'impressed': _('Impressed'),
    'in_awe': _('In Awe'),
    'in_love': _('In Love'),
    'indignant': _('Indignant'),
    'interested': _('Interested'),
    'intoxicated': _('Intoxicated'),
    'invincible': _('Invincible'),
    'jealous': _('Jealous'),
    'lonely': _('Lonely'),
    'lost': _('Lost'),
    'lucky': _('Lucky'),
    'mean': _('Mean'),
    'moody': _('Moody'),
    'nervous': _('Nervous'),
    'neutral': _('Neutral'),
    'offended': _('Offended'),
    'outraged': _('Outraged'),
    'playful': _('Playful'),
    'proud': _('Proud'),
    'relaxed': _('Relaxed'),
    'relieved': _('Relieved'),
    'remorseful': _('Remorseful'),
    'restless': _('Restless'),
    'sad': _('Sad'),
    'sarcastic': _('Sarcastic'),
    'satisfied': _('Satisfied'),
    'serious': _('Serious'),
    'shocked': _('Shocked'),
    'shy': _('Shy'),
    'sick': _('Sick'),
    'sleepy': _('Sleepy'),
    'spontaneous': _('Spontaneous'),
    'stressed': _('Stressed'),
    'strong': _('Strong'),
    'surprised': _('Surprised'),
    'thankful': _('Thankful'),
    'thirsty': _('Thirsty'),
    'tired': _('Tired'),
    'undefined': _('Undefined'),
    'weak': _('Weak'),
    'worried': _('Worried')
}

LOCATION_DATA = {
    'accuracy': _('accuracy'),
    'alt': _('alt'),
    'area': _('area'),
    'bearing': _('bearing'),
    'building': _('building'),
    'country': _('country'),
    'countrycode': _('countrycode'),
    'datum': _('datum'),
    'description': _('description'),
    'error': _('error'),
    'floor': _('floor'),
    'lat': _('lat'),
    'locality': _('locality'),
    'lon': _('lon'),
    'postalcode': _('postalcode'),
    'region': _('region'),
    'room': _('room'),
    'speed': _('speed'),
    'street': _('street'),
    'text': _('text'),
    'timestamp': _('timestamp'),
    'uri': _('URI')
}


SSLError = {
    2: _("Unable to get issuer certificate"),
    3: _("Unable to get certificate CRL"),
    4: _("Unable to decrypt certificate's signature"),
    5: _("Unable to decrypt CRL's signature"),
    6: _("Unable to decode issuer public key"),
    7: _("Certificate signature failure"),
    8: _("CRL signature failure"),
    9: _("Certificate is not yet valid"),
    10: _("Certificate has expired"),
    11: _("CRL is not yet valid"),
    12: _("CRL has expired"),
    13: _("Format error in certificate's notBefore field"),
    14: _("Format error in certificate's notAfter field"),
    15: _("Format error in CRL's lastUpdate field"),
    16: _("Format error in CRL's nextUpdate field"),
    17: _("Out of memory"),
    18: _("Self signed certificate"),
    19: _("Self signed certificate in certificate chain"),
    20: _("Unable to get local issuer certificate"),
    21: _("Unable to verify the first certificate"),
    22: _("Certificate chain too long"),
    23: _("Certificate revoked"),
    24: _("Invalid CA certificate"),
    25: _("Path length constraint exceeded"),
    26: _("Unsupported certificate purpose"),
    27: _("Certificate not trusted"),
    28: _("Certificate rejected"),
    29: _("Subject issuer mismatch"),
    30: _("Authority and subject key identifier mismatch"),
    31: _("Authority and issuer serial number mismatch"),
    32: _("Key usage does not include certificate signing"),
    50: _("Application verification failure"),
}


THANKS = u"""\
Alexander Futász
Alexander V. Butenko
Alexey Nezhdanov
Alfredo Junix
Anaël Verrier
Anders Ström
Andrew Sayman
Anton Shmigirilov
Christian Bjälevik
Christophe Got
Christoph Neuroth
David Campey
Dennis Craven
Fabian Neumann
Filippos Papadopoulos
Francisco Alburquerque Parra (Membris Khan)
Frederic Lory
Fridtjof Bussefor
Geobert Quach
Guillaume Morin
Gustavo J. A. M. Carneiro
Ivo Anjo
Josef Vybíral
Juraj Michalek
Kjell Braden
Luis Peralta
Michael Scherer
Michele Campeotto
Mike Albon
Miguel Fonseca
Norman Rasmussen
Oscar Hellström
Peter Saint-Andre
Petr Menšík
Sergey Kuleshov
Stavros Giannouris
Stian B. Barmen
Thilo Molitor
Thomas Klein-Hitpaß
Urtzi Alfaro
Witold Kieraś
Yakov Bezrukov
Yavor Doganov
""".strip().split("\n")

ARTISTS = u"""\
Anders Ström
Christophe Got
Dennis Craven
Dmitry Korzhevin
Guillaume Morin
Gvorcek Spajreh
Josef Vybíral
Membris Khan
Rederick Asher
Jakub Szypulka
""".strip().split("\n")

DEVS_CURRENT = u"""\
Yann Leboulanger (asterix AT lagaule.org)
Philipp Hörist (philipp AT hoerist.com)
""".strip().split("\n")

DEVS_PAST = u"""\
Stefan Bethge (stefan AT lanpartei.de)
Alexander Cherniuk (ts33kr AT gmail.com)
Stephan Erb (steve-e AT h3c.de)
Vincent Hanquez (tab AT snarc.org)
Dimitur Kirov (dkirov AT gmail.com)
Nikos Kouremenos (kourem AT gmail.com)
Julien Pivotto (roidelapluie AT gmail.com)
Jonathan Schleifer (js-gajim AT webkeks.org)
Travis Shirk (travis AT pobox.com)
Brendan Taylor (whateley AT gmail.com)
Jean-Marie Traissard (jim AT lapin.org)
""".strip().split("\n")
