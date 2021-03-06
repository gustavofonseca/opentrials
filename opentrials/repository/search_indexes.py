from haystack.indexes import SearchIndex, CharField, DateTimeField, BooleanField, MultiValueField, IntegerField
from haystack import site
from fossil.models import Fossil
from utilities import normalize_age

class FossilIndex(SearchIndex):
    text = CharField(document=True, use_template=False, stored=False)
    trial_id = CharField()
    rev_seq = CharField()
    is_most_recent = BooleanField()
    main_title = MultiValueField()
    rec_status = CharField(faceted=True)
    date_registration = DateTimeField()
    outdated = BooleanField()
    status = CharField()
    rec_country = MultiValueField()
    is_observational = BooleanField()
    i_type = MultiValueField(faceted=True)
    gender = CharField()
    minimum_recruitment_age = IntegerField() #in hours
    maximum_recruitment_age = IntegerField() #in hours


    def prepare_minimum_recruitment_age(self, obj):
        fossil_ct = obj.get_object_fossil()
        try:
            unit = fossil_ct.agemin_unit
            value = fossil_ct.agemin_value
        except:
            return None

        age = normalize_age(value, unit) if unit != '-' else 0

        return age

    def prepare_maximum_recruitment_age(self, obj):
        fossil_ct = obj.get_object_fossil()
        try:
            unit = fossil_ct.agemax_unit
            value = fossil_ct.agemax_value
        except:
            return None

        age = normalize_age(value, unit) if unit != '-' else normalize_age(200, 'Y')

        return age

    def prepare_trial_id(self, obj):
        fossil_ct = obj.get_object_fossil()
        try:
            return fossil_ct.trial_id
        except AttributeError:
            return None

    def prepare_rev_seq(self, obj):
        return obj.revision_sequential

    def prepare_is_most_recent(self, obj):
        return obj.is_most_recent

    def prepare_rec_status(self, obj):
        try:
            return obj.get_object_fossil().recruitment_status.label
        except AttributeError:
            return None

    def prepare_date_registration(self, obj):
        try:
            return obj.get_object_fossil().date_registration
        except AttributeError:
            return None

    def prepare_outdated(self, obj):
        try:
            return obj.get_object_fossil().outdated
        except AttributeError:
            return None

    def prepare_status(self, obj):
        try:
            return obj.get_object_fossil().status
        except AttributeError:
            return None

    def prepare_main_title(self, obj):
        fossil_ct = obj.get_object_fossil()
        fossil_ct._load_translations()

        try:
            main_titles = []
            for lang in fossil_ct._translations.keys():
                fossil_ct._language = lang
                main_titles.append(fossil_ct.main_title())

            return main_titles
        except AttributeError:
            return None

    def prepare_text(self, obj):
        fossil_ct = obj.get_object_fossil()
        fossil_ct._load_translations()

        retrieve_data_from = ['scientific_contacts', 'utrn_number', 'secondary_ids', 'trial_id', 'scientific_title',
          'public_title', 'acronym', 'scientific_acronym', 'scientific_acronym_expansion', 'hc_freetext', 'i_freetext']
        retrieve_data_from_multilanguage = ['scientific_title', 'public_title', 'acronym',
          'scientific_acronym', 'scientific_acronym_expansion', 'hc_freetext', 'i_freetext']

        all_text = set()
        for fossil_method in retrieve_data_from:
            try:
                all_text.add(getattr(fossil_ct, fossil_method))
            except AttributeError:
                pass

        for lang in fossil_ct._translations.keys(): #index content in all available languages
            fossil_ct._language = lang
            for fossil_method in retrieve_data_from_multilanguage:
                try:
                    all_text.add(getattr(fossil_ct, fossil_method))
                except AttributeError:
                    pass

        primary_sponsor = getattr(fossil_ct, 'primary_sponsor', '')
        if primary_sponsor:
            for v in primary_sponsor.values():
                if isinstance(v, basestring):
                    all_text.add(v)

        all_text.discard(None)
        return ' '.join(all_text).strip()

    def prepare_rec_country(self, obj):
        fossil_ct = obj.get_object_fossil()
        return [country['label'] for country in fossil_ct.recruitment_country]

    def prepare_is_observational(self, obj):
        fossil_ct = obj.get_object_fossil()
        return getattr(fossil_ct, 'is_observational', False)

    def prepare_i_type(self, obj):
        fossil_ct = obj.get_object_fossil()
        sources = []
        for source in fossil_ct.support_sources:
            try:
                sources.append(source['institution']['i_type']['label'])
            except KeyError:
                #field doesnt exist
                pass

        return sources

    def prepare_gender(self, obj):
        fossil_ct = obj.get_object_fossil()
        if fossil_ct.gender == 'M':
            return 'male'
        elif fossil_ct.gender == 'F':
            return 'female'
        else:
            return 'both'

site.register(Fossil, FossilIndex)
