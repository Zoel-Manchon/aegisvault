"""Word list for generated passphrases (Spanish, ASCII only).

Common, easy-to-type words with no accents or ñ, so a passphrase can be typed
on any keyboard layout. The list is de-duplicated at import; the generator
reports entropy from its real size (log2(len(WORDS)) bits per word).
"""
from __future__ import annotations

_RAW = """
abeja abrazo abrigo abuelo acero aceite acento acto agenda agosto agua aguila aire ajedrez
ala alba albergue alcalde aldea alegre alfombra algodon alma almendra almohada alpaca altar
alto altura alumno amable amigo ancho ancla angel anillo animal anis antena anzuelo aplauso
arana arbol arco arcilla arena arete argolla arista armario aroma arpa arroz arte asiento
astro atlas atleta atomo aula aurora autor avena aventura avion ayuda azafran azote azucar
azul bahia baile balcon balde ballena balsa bambu banco bandera banda bano barco barra barril
barro base basura bata bateria baul bebida becerro bello beso biblioteca bici bigote billete
bisonte boca boda bodega bola bolsa bombero bondad bonito borde bosque bota botella boton boxeo
brazo brisa broma brocha brujula bueno buey bufanda buho burbuja burro busca butaca caballo
cabana cabeza cable cabra cacao cactus cadena cadera cafe caja cajon calabaza calcetin caldo
calle calma calor cama camara camello camino camion camisa campana campo canal canasta cancion
candado canela cangrejo canoa cansado cantar canto capa capitan cara caracol carbon cardo carga
carne caro carpeta carrera carta casa cascada casco castillo catorce causa caza cebolla cebra
ceja celda cena centro cepillo cerca cerdo cereza cero cesta chaleco champu chaqueta charco
chispa chiste chocolate choza cielo ciervo cifra cigarra cine cinta circo ciruela cisne ciudad
clavel clima cobre coche cocina coco codo cofre cohete cojin col cola colchon colina collar
color columna comedor cometa comida cometer cono conejo copa coral corazon corbata corcho
cordero coro corona correo corte cosecha costa crater crema cristal cuaderno cuadro cuarto
cuatro cubo cuchara cuello cuenca cuento cuerda cuerno cuero cueva cultura cumbre cuna cupula
dado dama danza dardo datil debate decena dedo delfin denso deporte desierto destino detalle
diamante diario dibujo diente dieta disco dragon ducha duende dulce duna duque eco edad edificio
ejemplo elefante enero enigma ensalada entrada equipo escalera escoba escudo espacio espada
espejo espiga esponja esquina estatua estrella estufa etapa euro exito fabrica fachada falda
familia farol faro fiesta figura fila filete fin firma flauta flecha flor foca fogata fondo
forma foso foto fresa frio fruta fuego fuente fuerte furgon gafas gaita galaxia galleta gallo
ganso garaje garra gato gaviota gema genio gente gesto gigante girasol globo gnomo golfo goma
gorila gorra gota grada grano granja grillo grito grua grupo guante guarda guerra guitarra
gusano haba hacha hada halcon hamaca harina hebilla helado helecho herida hermano heroe hielo
hierba hierro higo hijo hilo hoguera hoja hombro hongo horno hotel hueco huerto hueso huevo
humo idea iglesia iguana imagen iman indice isla jabon jamon jardin jarra jaula jinete jirafa
joya joven juego jueves jugo juguete julio junio jurado kilo kiosco koala labio ladrillo lago
lagarto lamina lampara lana lapiz largo lata lavanda lazo leche lechuga leer legumbre lejos
lengua leon letra libro licor liga lima limon lince linea lino lirio lista litro llama llave
llegada lluvia lobo local lodo loma loro lucha luna lunes lupa luz madera madre maestro magia
maiz maleta malla mamut mango mano manta manzana mapa mar marco marea mareo margen marido
mariposa marmol martes martillo marzo mascara masa mastil matiz mayo mazo medalla media medico
mejilla melon menta mercado merienda mesa meta metro miel minuto mirada mitad mochila moda
molde molino moneda mono montana morado mosca motor mueble muela muelle muerte mujer mula mundo
muneca muro museo musica nabo nacion naranja nariz nata nave navaja nectar nido niebla nieve
nivel noble noche nombre norte nota noticia novela nube nuca nudo nuez numero nutria oasis obra
oceano ocho oeste oficina ojo ola oliva olivo olla ombligo onda opera orden oreja orgullo oro
orquesta oruga oso ostra otono oveja pablo paella pagina pais paja pajaro palabra palacio pala
paleta palma paloma pan panda panel panuelo papel paquete parada paraguas pared parque parrilla
parte paseo pasillo paso pasta pastel pata patata patio pato pausa pavo payaso peaje pecho
pedal peine pelota pena pera perla perro persona pesca peso petalo pez piano pico pie piedra
piel pierna pijama pila piloto pimienta pino pinza pinta pipa pirata piscina pista pizarra
placa plaga planeta planta plata plato playa plaza pluma pobre poema polen pollo polvo pomelo
poncho portal postre pozo prado premio primo prisma proa puente puerta puerto pulga pulpo pulso
punto pupitre queso quince quiosco rabano radio raiz rama rana rapido raton rayo razon real
receta red regalo regla reina reloj remo renta reptil resorte rey rincon rio risa ritmo rizo
roble roca rodilla rojo rombo ropa rosa rosal rubi rueda ruido ruta sabado sabana sable sabor
saco sal sala salmon salsa salto salud sandalia sandia sapo sardina sarten seda selva semana
semilla senda sendero senal seno sepia serpiente servilleta seta siglo silbato silla simio
sirena sitio sobre sofa sol soldado solo sombra sombrero sonido sopa soplo sorpresa sotano
suelo sueno suerte surco susto tabla taco tallo taller talon tambor tamiz tanque tapa tapiz
tarde tarea tarjeta tarro tarta taza teatro techo teja tejado tela telar tema templo tenedor
tenis tensor tercio termo ternura terraza tesoro tetera texto tiburon tiempo tienda tierra
tigre tijera tilde timbre tinta tio tiza toalla tobillo tomate tono topo torre tortuga tos
tostada trabajo tractor trama trapo trebol tren trigo trineo trompa tronco trono trucha trueno
tubo tulipan tumba tunel turno uva vaca vagon vaina valle valor vapor vaso vela velero vena
venado ventana verano verbo verde verso vestido viaje vida vidrio viento viernes villa vinagre
vino violin visita vista viuda vivo volcan voz vuelo yate yegua yema yerno yeso yoga yogur
zafiro zanahoria zapato zarza zona zorro zumo
abierto acuario adorno afecto agil agrio ajuste alamo alerta aljibe almacen amapola ambar
amuleto andamio anfora angulo apio archivo ardilla armonia arroyo atajo atun avellana azalea
bache bagaje bajel balanza banjo baraja barniz bastion batido bedel berenjena bisagra bizcocho
bloque bobina bocina bombilla boquete borrador bovino brasa brote bruma buzon cabestro cadete
caliz calzada cama campeon canica cantera canto capitel capullo carabela caramelo caravana
carpa carril cartel casino cauce caudal cebo cedro celeste cenit cerezo cerrojo cesped chacal
chalet charla chimenea chorizo cicatriz ciclon cilindro cima cinturon cipres circulo clase
clavo clinica cobijo codigo cojinete coleta comba compas concha condor consola copete cordel
corral cosmos costal coyote crisol cromo cronica cubierta cuervo cumbia cuota curva delta
dentista diadema dintel diploma divisa doblez docena domingo dorado dosis drama dueto eclipse
efecto eje elixir embudo emblema encina enlace ermita esbelto escala escaner esfera esmalte
establo estanque esteban estuche fabula faisan farmacia fauna felpa fiambre fideo filtro flan
flora florero forraje fosil fresno frontera fruta fulgor gacela galera galope gamba garbanzo
gardenia gasa gemelo geranio gimnasio glaciar golondrina gorrion granate granito greda guijarro
guinda guiso hangar harapo hechizo herradura hiedra hilera hipopotamo hormiga huella huracan
hurto indigo inicio insignia islote jaguar jazmin jengibre joyero jubilo junco kayak laberinto
lacre laguna lancha laurel lechuza legado leyenda libelula lienzo limite linterna lucero lustre
macizo madeja magnolia malva mamey mandala manantial mantel mantis marfil marisco mastin matraz
mecha medusa mejillon meseta mimbre mirlo mocasin molusco monarca morera mortero mosaico
muestra murmullo nacar narciso naufragio neblina nenufar nogal nomada nucleo obsidiana ocaso
octavo ombu orbita orquidea ortiga osadia pagoda palmera pampa panal pantano papiro parche
partitura pastor patrulla pelicano peldano penacho pendiente perdiz pergola pilar pinguino
pinar pinacho piramide platano plomo pluton podio polea pomo porton potro pradera prisma pua
puma quetzal quimera quinoa quinta rafaga rebano recodo refugio relampago reliquia remanso
retablo retama rocio romero rompeolas rubor rumbo sabueso salitre salvia sauce sello sequoia
serrin sextante silbido silueta sinfonia sintonia soga solapa sonaja sorbete sorgo suspiro
tabique talisman tamarindo tapir tarima tejon telon tempano tenaza terciopelo tomillo topacio
torbellino tormenta torrente tranvia trinchera triton trompeta tropel tucan turbante turquesa
umbral unicornio urraca utopia vainilla vendaval veleta ventisca verbena vereda vergel vertice
vesta vigia vinedo violeta virtud vitral vivero volante yunque zagal zambomba zarpa zocalo
zumbido
"""

WORDS: tuple[str, ...] = tuple(sorted({
    w for w in _RAW.split() if w.isascii() and w.isalpha() and 3 <= len(w) <= 10
}))
