 //Function to open the GPS map
function openMap(id) {
    //Close all iframes
    let x = document.getElementsByClassName("map");
    let i;
    for (i = 0; i < x.length; i++) {
        x[i].hidden = true;
    }
    //Show the element with id="jsonSrc"
    document.getElementById(id).hidden = false;
}
