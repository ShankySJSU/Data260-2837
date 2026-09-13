
"use strict"; // enables strict mode and enforces stricter parsing
console.log("restfeedback.js is loaded successfully.");

const totalSubmissonCount = (() => {
    let count = 0;
    return () => {
        count++;
        return count;
    };
})();

function showLoading() {
    document.getElementById("loadingState").style.display = "block";
}

function hideLoading() {
    document.getElementById("loadingState").style.display = "none";
}

function showEmptyState() {
    document.getElementById("emptyState").style.display = "block";
}

function hideEmptyState() {
    document.getElementById("emptyState").style.display = "none";
}
function showError(msg) {
    const e = document.getElementById("errorState");
    e.innerText = msg;
    e.style.display = "block";
}

function hideError() {
    const e = document.getElementById("errorState");
    e.innerText = "";
    e.style.display = "none";
}

function renderRecordList(records) {
    const container = document.getElementById("recordList");
    container.innerHTML = "";

    records.forEach(rec => {
        const card = `
            <div style="background:white; padding:15px; margin-bottom:15px; border-radius:8px;
                        box-shadow:0 2px 8px rgba(0,0,0,0.1);">
                <h3 style="margin-top:0;">${rec.restaurantName}</h3>
                <p><strong>Address:</strong> ${rec.restAddress}</p>
                <p><strong>Email:</strong> ${rec.inspectorEmail}</p>
                <p><strong>Notes:</strong> ${rec.inspectionNotes}</p>
                <p><strong>Category:</strong> ${rec.inspectionCategory}</p>
                <p><strong>Submitted:</strong> ${rec.submittedAt}</p>
            </div>
        `;
        container.innerHTML += card;
    });
}

async function loadRecords() {
    showLoading();
    hideError();
    hideEmptyState();

    try {
        const resp = await fetch("http://localhost:8137/restaurants");
        const data = await resp.json();

        hideLoading();

        if (data.length === 0) {
            showEmptyState();
        } else {
            renderRecordList(data);
        }
    } catch (error) {
        hideLoading();
        showError("Failed to load records.");
    }
}

document.getElementById("inspectionForm").addEventListener("submit", async (e) => {

    e.preventDefault(); // Prevent refresh

    // Collect form values ONLY ONCE
    const formValues = {
        restName: document.getElementById("restName").value.trim(),
        restAdr: document.getElementById("restAddress").value.trim(),
        email: document.getElementById("inspectorEmail").value.trim(),
        comments: document.getElementById("comments").value.trim(),
        inspectionCat: document.getElementById("inspectionCat").value,
        termsChecked: document.getElementById("cbTermAndCond").checked,
        submittedAt: new Date().toLocaleString()
    };

    // Validate form using arrow function, passing the values
    if (!validateForm(formValues)) return;

    // HW2: Send to FastAPI backend
    try {
        const response = await fetch("http://localhost:8137/restaurants", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
                restaurantName: formValues.restName,
                restAddress: formValues.restAdr,
                inspectorEmail: formValues.email,
                inspectionNotes: formValues.comments,
                inspectionCategory: formValues.inspectionCat,
                submittedAt: formValues.submittedAt
            })
        });

        const data = await response.json();
        console.log("Backend received:", data);

    } catch (error) {
        console.error("Backend submission error:", error);
        showError("Could not submit to server.");
    }

    alert("Thanks! Your Inspection Report has been Submitted Successfully!");

    const formValuesJSON = JSON.stringify(formValues);
    console.log("log:Inspection Form Submission with following values:", formValuesJSON);



    const parsedFormObj = JSON.parse(formValuesJSON);

    //now do the object destrcuing and read priamry file and submitted email address
    const { restName, email } = parsedFormObj;  
    console.log("Primary Field -->(Restaurant Name):", restName);
    console.log("Email Field-->(Inspector email):", email);

    //creating a spread operator to add submitted data entries
    const formWithSubmissonDt = {
        ...parsedFormObj,
        submittedAt: new Date().toLocaleString()
    };

    console.log("Log:Submiited form values with submission date and time:", formWithSubmissonDt);

    //also log how mnay time the form has been submitted

    const noOfSubmission = totalSubmissonCount();
    console.log("Count of Successfull submission till now:", noOfSubmission);


    document.getElementById("inspectionForm").reset();
});


// ---------------------------------------------------------
// CLEAN VALIDATION FUNCTION (arrow function)
// ---------------------------------------------------------
const validateForm = (vals) => {

    if (!vals.termsChecked) {
        alert("You must agree to the terms and conditions.Please select T&A checkbox");
        return false;
    }

    if (!vals.restName) {
        alert("Restaurant Name cannot be empty.");
        return false;
    }

    if (!vals.restAdr) {
        alert("Restaurant Address cannot be empty.");
        return false;
    }

    if (!vals.email) {
        alert("Inspector Email cannot be empty.");
        return false;
    }

    if (!vals.comments) {
        alert("Inspection Notes cannot be empty.");
        return false;
    }

    if (!vals.inspectionCat || vals.inspectionCat === "") {
        alert("Please select an inspection category.");
        return false;
    }

    if (vals.comments.length < 25) {
        alert("Inspection Notes/Comments have minimum requirements of 25 characters. You entered only " + vals.comments.length );
        return false;
    }

    return true; // All good
};

loadRecords();