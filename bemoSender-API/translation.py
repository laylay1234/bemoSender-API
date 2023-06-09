from modeltranslation.translator import register, TranslationOptions
from bemosenderrr.models.partner.partner import Country, MobileNetwork, TransactionMethod


@register(Country)
class CountryTranslationOptions(TranslationOptions):
    fields = ('name',)


@register(MobileNetwork)
class MobileNetworkTranslationOptions(TranslationOptions):
    fields = ('display_name',)


@register(TransactionMethod)
class TransactionMethodTranslationOptions(TranslationOptions):
    fields = ('name',)