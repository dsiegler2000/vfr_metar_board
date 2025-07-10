function parseCsv(data, delimiter){
    // Default delimiter to ","
    delimiter = (delimiter || ",");

    var objPattern = new RegExp(
        (
            // Delimeters
            "(\\" + delimiter + "|\\r?\\n|\\r|^)" +

            // Quoted fields
            "(?:\"([^\"]*(?:\"\"[^\"]*)*)\"|" +

            // Standard fields
            "([^\"\\" + delimiter + "\\r\\n]*))"
        ),
        "gi"
    );

    // Output array
    var dataOut = [[]];

    // Regex matches
    var arrMatches = null;


    // Keep looping over regex patterns until we no longer see a match
    while (arrMatches = objPattern.exec(data)){

        // Get match
        var strMatchedDelimiter = arrMatches[1];

        // If the matched delimiter has length but isn't the defined delimeter, end of line
        if (strMatchedDelimiter.length && (strMatchedDelimiter != delimiter)){

            // Push new row to array (for next text row)
            dataOut.push([]);
        }

        // Check for data - handle both quoted & unquoted cases
        var strMatchedValue = arrMatches[2] ? arrMatches[2].replace(new RegExp("\"\"", "g"), "\"") : arrMatches[3];

        // Push value to array
        dataOut[dataOut.length - 1].push(strMatchedValue);
    }

    return dataOut;
}
