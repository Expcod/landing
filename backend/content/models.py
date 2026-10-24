from django.core.validators import RegexValidator
from django.db import models


class Ordered(models.Model):
    order = models.PositiveIntegerField('Тартиб', default=0)
    active = models.BooleanField('Сайтда кўрсатилсин', default=True)

    class Meta:
        abstract = True
        ordering = ['order', 'id']


class Client(Ordered):
    name = models.CharField('Номи', max_length=100)
    logo = models.FileField('Логотип', upload_to='clients/', blank=True)

    class Meta(Ordered.Meta):
        verbose_name = 'Мижоз (логотиплар қатори)'
        verbose_name_plural = 'Мижозлар (логотиплар қатори)'

    def __str__(self):
        return self.name


class Case(Ordered):
    who = models.CharField('Мижоз', max_length=100)
    industry = models.CharField('Соҳа', max_length=150, help_text='масалан: бетон ва асфальт заводи')
    logo = models.FileField('Логотип', upload_to='cases/', blank=True)
    num = models.CharField('Натижа рақами', max_length=60, help_text='масалан: 70–80 млн сўм')
    short = models.CharField('Қисқа изоҳ (биринчи экран)', max_length=120, help_text='масалан: 1 ойда тежалди')
    line = models.CharField('Тўлиқ изоҳ (кейслар бўлими)', max_length=300)
    before_label = models.CharField('Олдин — матн', max_length=100)
    before_pct = models.PositiveSmallIntegerField('Олдин — полоса, %', default=30)
    after_label = models.CharField('Кейин — матн', max_length=100)
    after_pct = models.PositiveSmallIntegerField('Кейин — полоса, %', default=100)
    in_hero = models.BooleanField('Биринчи экранда ҳам кўрсатилсин', default=True)

    class Meta(Ordered.Meta):
        verbose_name = 'Кейс (лойиҳа натижаси)'
        verbose_name_plural = 'Кейслар (лойиҳа натижалари)'

    def __str__(self):
        return self.who


class Screen(Ordered):
    tag = models.CharField('Белги', max_length=60)
    title = models.CharField('Сарлавҳа', max_length=150)
    image = models.ImageField('Скриншот', upload_to='screens/')
    max_width = models.PositiveIntegerField('Расм максимал эни, px', default=600)
    points = models.TextField('Пунктлар', help_text='Ҳар бир пункт алоҳида қаторда')

    class Meta(Ordered.Meta):
        verbose_name = 'Экран (скриншот)'
        verbose_name_plural = 'Экранлар (скриншотлар)'

    def __str__(self):
        return self.title


class Reel(Ordered):
    caption = models.CharField('Изоҳ', max_length=200)
    video = models.FileField('Видео (mp4)', upload_to='reels/', blank=True)
    video_url = models.URLField('ёки видео манзили (mp4)', blank=True)
    poster = models.ImageField('Муқова расми', upload_to='reels/', blank=True)
    poster_url = models.URLField('ёки муқова манзили', blank=True)
    instagram_url = models.URLField('Instagram ҳаволаси', blank=True)

    class Meta(Ordered.Meta):
        verbose_name = 'Видео (reels)'
        verbose_name_plural = 'Видеолар (reels)'

    def __str__(self):
        return self.caption


class Lead(models.Model):
    STATUSES = [('new', 'Янги'), ('called', 'Қўнғироқ қилинди'), ('meeting', 'Аудит белгиланди'), ('rejected', 'Рад этилди')]

    created = models.DateTimeField('Вақти', auto_now_add=True)
    name = models.CharField('Исм', max_length=150)
    phone = models.CharField('Телефон', max_length=40)
    business = models.CharField('Фаолият тури', max_length=200, blank=True)
    problem = models.TextField('Ҳозирги муаммо', blank=True)
    page = models.CharField('Саҳифа', max_length=500, blank=True)
    ip = models.GenericIPAddressField('IP', null=True, blank=True)
    status = models.CharField('Ҳолати', max_length=20, choices=STATUSES, default='new')
    note = models.TextField('Изоҳ (менеджер учун)', blank=True)
    sid = models.CharField('Ташриф', max_length=40, blank=True)
    odoo_id = models.PositiveIntegerField('Odoo CRM ID', null=True, blank=True)
    tg_sent = models.BooleanField("Telegram'га юборилди", default=False)
    sync_error = models.TextField('Юбориш хатоси', blank=True)

    class Meta:
        ordering = ['-created']
        verbose_name = 'Ариза'
        verbose_name_plural = 'Аризалар'

    def __str__(self):
        return f'{self.name} {self.phone}'


class SiteSettings(models.Model):
    pixel_id = models.CharField('Meta Pixel ID', max_length=30, blank=True,
                                help_text='Фақат рақамлар, масалан: 1234567890123456. Бўш қолса, Pixel уланмайди.',
                                validators=[RegexValidator(r'^\d*$', 'Pixel ID фақат рақамлардан иборат бўлади.')])
    tg_token = models.CharField('Telegram бот токени', max_length=100, blank=True)
    odoo_url = models.URLField('Odoo манзили', blank=True, help_text='масалан: https://demo.novaodoo.uz')
    odoo_db = models.CharField('Odoo базаси', max_length=100, blank=True)
    odoo_api_key = models.CharField('Odoo API калити', max_length=100, blank=True)

    class Meta:
        verbose_name = 'Созламалар'
        verbose_name_plural = 'Созламалар'

    def __str__(self):
        return 'Сайт созламалари'

    @classmethod
    def get(cls):
        return cls.objects.get_or_create(pk=1)[0]


class TgSubscriber(models.Model):
    """Ботга /start босган одам ёки бот қўшилган гуруҳ.

    Аризалар фақат админ рухсат берганларга (status=approved) ва /stop босмаганларга (active) боради.
    Админ (раҳбар) янги обуначига ботнинг ўзида «Рухсат бериш / Йўқ» тугмаси билан жавоб беради.
    """
    PENDING, APPROVED, REJECTED = 'pending', 'approved', 'rejected'
    STATUSES = [(PENDING, 'Рухсат кутилмоқда'), (APPROVED, 'Рухсат берилган'), (REJECTED, 'Рад этилган')]

    chat_id = models.BigIntegerField('Чат ID', unique=True)
    name = models.CharField('Исм / гуруҳ', max_length=200, blank=True)
    username = models.CharField('Username', max_length=100, blank=True)
    is_group = models.BooleanField('Гуруҳ', default=False)
    is_admin = models.BooleanField('Админ (рухсат беради)', default=False,
                                   help_text='Янги обуначилар учун рухсат сўрови шу одамларга боради.')
    status = models.CharField('Рухсат', max_length=10, choices=STATUSES, default=PENDING)
    active = models.BooleanField('Обуна ёқиқ', default=True, help_text='/stop босса ёки ботни блокласа ўчади.')
    created = models.DateTimeField('Қўшилган', auto_now_add=True)

    class Meta:
        ordering = ['-created']
        verbose_name = 'Telegram обуначи'
        verbose_name_plural = 'Telegram обуначилар'

    def __str__(self):
        return self.name or str(self.chat_id)


class Visit(models.Model):
    """Сайтга битта кириш (сессия). Маълумот сайтдаги content.js'дан келади."""
    sid = models.CharField(max_length=40, unique=True)
    vid = models.CharField('Меҳмон', max_length=40, db_index=True)
    started = models.DateTimeField('Кирган вақти', auto_now_add=True, db_index=True)
    last_seen = models.DateTimeField('Охирги фаоллик', auto_now=True)
    duration = models.PositiveIntegerField('Сайтда вақт, сек', default=0)
    max_scroll = models.PositiveSmallIntegerField('Қаергача тушди, %', default=0)
    last_section = models.CharField('Чиқиб кетган бўлим', max_length=30, blank=True)
    max_section = models.CharField('Энг пастки бўлим', max_length=30, blank=True)
    source = models.CharField('Манба', max_length=100, blank=True)
    campaign = models.CharField('Кампания', max_length=150, blank=True)
    referrer = models.CharField(max_length=300, blank=True)
    device = models.CharField('Қурилма', max_length=10, blank=True)
    ip = models.GenericIPAddressField(null=True, blank=True)
    ua = models.CharField(max_length=300, blank=True)

    class Meta:
        ordering = ['-started']
        verbose_name = 'Ташриф'
        verbose_name_plural = 'Ташрифлар'

    def __str__(self):
        return f'{self.started:%d.%m %H:%M} {self.source}'


class Event(models.Model):
    visit = models.ForeignKey(Visit, on_delete=models.CASCADE, related_name='events')
    name = models.CharField(max_length=40, db_index=True)
    label = models.CharField(max_length=200, blank=True)
    created = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['created']
