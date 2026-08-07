"""Nederlandse voornamen — om rol-adressen van persoonlijke te onderscheiden.

Zonder deze check wordt `betalingen@bedrijf.nl` als persoonlijk gezien en
belandt "Betalingen" als voornaam in je mailmerge. Eén zo'n rij verpest een
hele campagne, dus de regel is streng: één woord vóór de @ telt alleen als
voornaam wanneer het écht een voornaam is.
"""

from __future__ import annotations

VOORNAMEN: frozenset[str] = frozenset("""
aad aaltje aart abdel abdullah achmed ad adam adrian adriaan adrie agnes ahmed
ahmet ailin ajax albert alberta albertus aldert alex alexander alexandra alfred
ali alice alicia aline alissa allard alwin amber amina amir amy ana anders andre
andrea andries andy anita anja anna anne anneke annelies annemarie annemieke
annet annette anouk ans anthonie anton antoine antoinette antonia arend ari
arie arjan arjen arnold arno arnoud arthur ashley astrid aukje ayla ayse bart
barbara barend bas bastiaan beatrice beatrix bella ben benjamin benno benny
bep berend bernard bernadette bert bertus bianca bill bo bob boris bram brenda
brian bruno burak caitlin camiel carel carin carla carlijn carmen carola
carolien caroline casper catharina cathy cees celine chantal charlene charles
charlotte chiara chris christa christiaan christian christina christine
cindy claire clara claudia clemens colin conny cor cora corine cornelia
cornelis corrie coen daan daniel daniella danielle danny dave david dawn dean
debbie deborah demi denise dennis derk desiree diana dick diederik dieter dik
dimitri dion dirk dominique don donna dora dorien doris douwe duco dylan
edith edwin egbert eline elisabeth eliza elizabeth ella ellen elly elmar
els elsbeth emma emiel emil emily enzo eric erik erna ernst erwin esmee
esther eva evelien evert ewout fabian farah fatima felix femke ferdinand
ferry fien fleur flip floor floris frank frans franciska frederik frits
gaby geert geertje geertruida gemma gerard gerben gerd gerhard gerrie
gerrit gert gertjan gijs gina gonda govert greet greta guido gus gustav
hakan hanna hannah hanneke hans harm harold harrie harry hasan heidi hein
heleen helena helma hendrik hendrika henk henriette henry herbert herman
hessel hidde hilde hillie hugo huib huub ibrahim ida ilse ilona imke ina
inge ingrid irene iris isa isabel isabella isabelle ismail ivan ivo iwan
jaap jack jacob jacqueline jacobus jamal james jan jana janine janneke
jannie jantien jasper jean jeanette jeanne jelle jelmer jennifer jenny
jeroen jesse jessica jill jim jimmy jitske joachim joan joanne job jochem
joep joeri johan johanna johannes john johnny jolanda jolijn jonas jonathan
joop joost jordi jorg jorik joris jos jose josephine joyce jozef judith
juliette julia julian juliana june jurgen jurjen justin jvon kaan karel
karen karin karina karlijn kaspar kate katharina katja kay kees kelly
kevin khalid kim kirsten klaas klaus koen koert konrad koos kristel
kyra laura laurens lea lena lennart lenny leo leon leonard leontien
lex lia lianne lida lidewij lieke lilian linda linde lisa lisanne lisette
liset liza lodewijk loek lotte louis louise lourens luc luca lucas lucia
lucie ludo luuk lydia maaike maarten machteld madelon maik maike mandy
manon manuel marc marcel marco marcus margot margriet maria marian
mariann marianne marielle marije marijke marijn marina mario marion
marise marit marja marjolein mark marleen marlies marloes marnix
martha martijn martin martine marty mary mathijs matthijs maud maurice
maurits max maya mehmet melanie melissa menno merel mert michael michel
michiel mieke miguel mike milan mila milou mira mirjam mireille miriam
mirte mitchell mohamed mohammed moniek monique murat mustafa myrthe
nadia nancy naomi natalie natasja nathalie neeltje nick nico nicole
nicolette niek niels nienke nikki nils nina noor noortje norbert olaf
olga oliver olivia omar onno oscar otto paola pascal patricia patrick
paul paula paulien pauline peter petra petronella phil philip pien piet
pieter pim priscilla puck quinten rachel rafael ralph ramon randy raoul
raymond rebecca reinier reinout remco remy renata rene renee renske
rick rian richard rick rien rik rina rinus rita rob robbert robert
robin rochelle rody roel roelof roger roland rolf romy ron ronald
ronnie roos roosmarijn rosa rosalie roxanne rudi rudolf ruud ruben
ruth ryan sabine sabrina sacha salim sam samantha samir sander sandra
sanne sara sarah sascha saskia scott sebastiaan selma sem semih serge
sharon sheila sibbe sicco siebe siem sietse sigrid silke silvia simon
simone sjaak sjoerd sofie sonja sophia sophie stan stefan stefanie
steffen stella sten stephanie steve steven stijn suzanne sven sybren
sylvia tamara tanja tara ted teun teunis thea theo thera thijs thomas
tijmen tim timo timothy tineke tinus titia tjeerd tobias tom tommy toon
tosca trees trudy tycho ubbo ulrike ursula valerie vanessa veerle vera
victor victoria vincent vivian walter ward wendy werner wessel wibe wies
wil wilbert wilfred wilfried wilhelmina willem willemien willy wim
wobbe wouter xander yara yasmin yolanda yousef yvette yvonne zeynep zoe
""".split())


def is_voornaam(token: str) -> bool:
    """Is dit losse woord een plausibele Nederlandse voornaam?"""
    return token.strip().lower() in VOORNAMEN
