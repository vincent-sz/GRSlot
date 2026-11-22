#define P5_DESC_BASE 0x541e7cd8u
#define P5_PIXELS 0x541e7f78u
#define GLYPH_ACTION_BACK ((const U*)0x5412f344u)
#define GLYPH_ACTION_INFO ((const U*)0x54130344u)
#define GLYPH_ACTION_INSTALL ((const U*)0x54131344u)
#define GLYPH_CATEGORY_ALL ((const U*)0x54132344u)
#define GLYPH_CATEGORY_BW ((const U*)0x54133344u)
#define GLYPH_CATEGORY_DIGITAL ((const U*)0x54134344u)
#define GLYPH_CATEGORY_FAVORITES ((const U*)0x54135344u)
#define GLYPH_CATEGORY_FUJIFILM ((const U*)0x54136344u)
#define GLYPH_CATEGORY_KODAK ((const U*)0x54137344u)
#define GLYPH_CATEGORY_MY_LUTS ((const U*)0x54138344u)
#define GLYPH_CATEGORY_OTHER ((const U*)0x54139344u)
struct category {const char*id;const uint16_t*name;U kind;const U*glyph;};
static const struct category categories[]={
{"__all",u"All Films",2,GLYPH_CATEGORY_ALL},
{"favorites",u"Favorites",1,GLYPH_CATEGORY_FAVORITES},
{"kodak",u"Kodak",0,GLYPH_CATEGORY_KODAK},
{"fujifilm",u"Fujifilm",0,GLYPH_CATEGORY_FUJIFILM},
{"bw",u"B&W",0,GLYPH_CATEGORY_BW},
{"digital",u"Digital Cameras",0,GLYPH_CATEGORY_DIGITAL},
{"other",u"Other Films",0,GLYPH_CATEGORY_OTHER},
{"my-luts",u"My LUTs",0,GLYPH_CATEGORY_MY_LUTS},
};
#define CATEGORY_COUNT (sizeof(categories)/sizeof(categories[0]))
struct metadata {U category,favorite;const uint16_t*short_name;};
static const struct metadata metadata[]={{2u,0u,film_name_1},{2u,0u,film_name_2},{5u,0u,film_name_3},{3u,0u,film_name_4},{2u,0u,film_name_5},{2u,0u,film_name_6},{2u,0u,film_name_7},{3u,0u,film_name_8},{3u,0u,film_name_9},{3u,0u,film_name_10},{2u,0u,film_name_11},{2u,0u,film_name_12},{2u,0u,film_name_13},{2u,0u,film_name_14},{2u,0u,film_name_15},{2u,0u,film_name_16},{2u,0u,film_name_17},{2u,0u,film_name_18},{2u,0u,film_name_39},{5u,0u,film_name_40},{5u,0u,film_name_41},{5u,0u,film_name_42},{3u,0u,film_name_43},{3u,0u,film_name_44},{6u,0u,film_name_45},{3u,0u,film_name_46},{3u,0u,film_name_47},{3u,0u,film_name_48},{3u,0u,film_name_49},{3u,0u,film_name_50},{3u,0u,film_name_51},{3u,0u,film_name_52},{3u,0u,film_name_53},{3u,0u,film_name_54},{2u,0u,film_name_55},{2u,0u,film_name_56},{2u,0u,film_name_57},{2u,0u,film_name_58},{2u,0u,film_name_59},{2u,0u,film_name_60},{2u,0u,film_name_61},{2u,0u,film_name_62},{2u,0u,film_name_63},{2u,0u,film_name_64},{2u,0u,film_name_65},{2u,0u,film_name_66},{2u,0u,film_name_67},{2u,0u,film_name_68},{2u,0u,film_name_69},{2u,0u,film_name_70},{2u,0u,film_name_71},{2u,0u,film_name_72},{2u,0u,film_name_73},{2u,0u,film_name_74},{2u,0u,film_name_75},{2u,0u,film_name_76},{2u,0u,film_name_77},{2u,0u,film_name_78},{2u,0u,film_name_79}};
static const U film_order[]={0,1,2,3,4,5,6,7,8,9,10,11,12,13,14,15,16,17,18,19,20,21,22,23,24,25,26,27,28,29,30,31,32,33,34,35,36,37,38,39,40,41,42,43,44,45,46,47,48,49,50,51,52,53,54,55,56,57,58};
static const U category_counts[]={59,0,39,15,0,4,1,0};
static const uint16_t*const count_labels[]={u"0",u"1",u"2",u"3",u"4",u"5",u"6",u"7",u"8",u"9",u"10",u"11",u"12",u"13",u"14",u"15",u"16",u"17",u"18",u"19",u"20",u"21",u"22",u"23",u"24",u"25",u"26",u"27",u"28",u"29",u"30",u"31",u"32",u"33",u"34",u"35",u"36",u"37",u"38",u"39",u"40",u"41",u"42",u"43",u"44",u"45",u"46",u"47",u"48",u"49",u"50",u"51",u"52",u"53",u"54",u"55",u"56",u"57",u"58",u"59",u"60",u"61",u"62",u"63",u"64",u"65",u"66",u"67",u"68",u"69",u"70",u"71",u"72",u"73",u"74",u"75",u"76",u"77",u"78",u"79",u"80",u"81",u"82",u"83",u"84",u"85",u"86",u"87",u"88",u"89",u"90",u"91",u"92",u"93",u"94",u"95",u"96",u"97",u"98",u"99",u"100",u"101"};
static const char*const grid_titles[][17]={
{"All Films 1/7","All Films 2/7","All Films 3/7","All Films 4/7","All Films 5/7","All Films 6/7","All Films 7/7"},
{"Favorites 1/1"},
{"Kodak 1/5","Kodak 2/5","Kodak 3/5","Kodak 4/5","Kodak 5/5"},
{"Fujifilm 1/2","Fujifilm 2/2"},
{"B&W 1/1"},
{"Digital Cameras 1/1"},
{"Other Films 1/1"},
{"My LUTs 1/1"},
};
static const char*const category_titles[]={"Film Library 1/2","Film Library 2/2"};
